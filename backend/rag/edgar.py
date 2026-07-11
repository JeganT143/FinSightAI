"""SEC EDGAR client (ADR-5).

EDGAR is free and keyless; the SEC only requires a User-Agent identifying the
requester and fair-use rates (<10 req/s — we make 3 requests per ingestion).
"""

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from backend.core.config import settings

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{doc}"

_HEADERS = {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}

# Module-level cache: ticker -> CIK. The mapping file is ~1MB and changes rarely.
_cik_cache: dict[str, str] = {}


@dataclass
class FilingMeta:
    ticker: str
    cik: str
    form_type: str
    accession_no: str
    filing_date: str
    primary_document: str

    @property
    def url(self) -> str:
        return _ARCHIVE_URL.format(
            cik_int=int(self.cik),
            accession_nodash=self.accession_no.replace("-", ""),
            doc=self.primary_document,
        )


class EdgarError(Exception):
    """Raised when EDGAR data is unavailable — callers degrade gracefully, never crash a run."""


async def lookup_cik(client: httpx.AsyncClient, ticker: str) -> str:
    if not _cik_cache:
        resp = await client.get(_TICKER_MAP_URL, headers=_HEADERS)
        resp.raise_for_status()
        for entry in resp.json().values():
            _cik_cache[entry["ticker"].upper()] = str(entry["cik_str"])
    cik = _cik_cache.get(ticker.upper())
    if not cik:
        raise EdgarError(f"No SEC CIK found for ticker {ticker!r} (not a US-listed filer?)")
    return cik


async def latest_filing(
    client: httpx.AsyncClient, ticker: str, forms: tuple[str, ...] = ("10-K", "10-Q")
) -> FilingMeta:
    """Most recent filing of the first form type that exists (10-K preferred)."""
    cik = await lookup_cik(client, ticker)
    resp = await client.get(_SUBMISSIONS_URL.format(cik=cik), headers=_HEADERS)
    resp.raise_for_status()
    recent = resp.json().get("filings", {}).get("recent", {})
    form_list = recent.get("form", [])

    for wanted in forms:
        for i, form in enumerate(form_list):
            if form == wanted:
                return FilingMeta(
                    ticker=ticker.upper(),
                    cik=cik,
                    form_type=form,
                    accession_no=recent["accessionNumber"][i],
                    filing_date=recent["filingDate"][i],
                    primary_document=recent["primaryDocument"][i],
                )
    raise EdgarError(f"No {'/'.join(forms)} filings found for {ticker}")


async def fetch_filing_text(client: httpx.AsyncClient, meta: FilingMeta) -> str:
    """Download the primary document and reduce HTML to whitespace-normalized text."""
    resp = await client.get(meta.url, headers=_HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse runs of blank lines / spaces but keep paragraph breaks.
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
