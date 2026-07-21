"""EDGAR client tests against httpx.MockTransport — no network, real parsing.

These pin the behaviors ARCHITECTURE.md promises: 10-K preferred over a more
recent 10-Q, typed EdgarError (never a crash) for non-filers, and HTML
reduced to clean text with scripts/styles stripped.
"""

import httpx
import pytest

from backend.rag import edgar

_SUBMISSIONS = {
    "filings": {
        "recent": {
            # 10-Q is MORE RECENT than the 10-K — form preference must still win.
            "form": ["8-K", "10-Q", "10-K"],
            "accessionNumber": ["0001-24-000001", "0001-24-000002", "0001-24-000003"],
            "filingDate": ["2026-06-01", "2026-05-01", "2026-02-14"],
            "primaryDocument": ["ev.htm", "q1.htm", "annual.htm"],
        }
    }
}


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.endswith("company_tickers.json"):
        return httpx.Response(
            200, json={"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"}}
        )
    if "data.sec.gov/submissions" in url:
        return httpx.Response(200, json=_SUBMISSIONS)
    if url.endswith("annual.htm"):
        html = (
            "<html><script>tracking()</script><style>.x{}</style>"
            "<body><p>Item 1A.   Risk\xa0Factors</p>\n\n\n<p>Real   content.</p></body></html>"
        )
        return httpx.Response(200, text=html)
    return httpx.Response(404, text="not found")


@pytest.fixture
def client(monkeypatch):
    # Fresh CIK cache per test — it's a module-level dict by design.
    monkeypatch.setattr(edgar, "_cik_cache", {})
    return httpx.AsyncClient(transport=httpx.MockTransport(_handler))


async def test_latest_filing_prefers_10k_over_newer_10q(client):
    meta = await edgar.latest_filing(client, "nvda")
    assert meta.form_type == "10-K"
    assert meta.filing_date == "2026-02-14"
    assert meta.ticker == "NVDA"
    assert meta.cik == "1045810"
    assert meta.url.endswith("annual.htm")
    assert "/1045810/" in meta.url  # CIK without zero-padding in archive URLs


async def test_unknown_ticker_raises_typed_error(client):
    with pytest.raises(edgar.EdgarError, match="ZZZZ"):
        await edgar.lookup_cik(client, "ZZZZ")


async def test_no_matching_forms_raises_typed_error(client):
    with pytest.raises(edgar.EdgarError, match="No 10-K/A filings"):
        await edgar.latest_filing(client, "NVDA", forms=("10-K/A",))


async def test_fetch_filing_text_strips_scripts_and_collapses_whitespace(client):
    meta = await edgar.latest_filing(client, "NVDA")
    text = await edgar.fetch_filing_text(client, meta)
    assert "tracking()" not in text
    assert ".x{}" not in text
    assert "Item 1A. Risk Factors" in text  # nbsp + runs of spaces collapsed
    assert "\n\n\n" not in text  # blank-line runs collapsed
