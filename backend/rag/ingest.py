"""Filing ingestion: EDGAR -> sections -> chunks -> embeddings -> pgvector.

Idempotent per accession number: researching the same ticker again skips
straight to retrieval (first-run cost ~10-20s and ~$0.002 of embeddings).
"""

import logging
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Filing, FilingChunk
from backend.rag import edgar
from backend.rag.chunking import chunk_filing
from backend.rag.embeddings import embed_texts

logger = logging.getLogger(__name__)


@dataclass
class IngestStatus:
    status: str  # "ingested" | "cached" | "unavailable"
    detail: str
    form_type: str | None = None
    filing_date: str | None = None
    chunk_count: int = 0
    embedding_cost_usd: float = 0.0


async def ensure_filing_ingested(db: AsyncSession, ticker: str) -> IngestStatus:
    """Make sure the latest 10-K/10-Q for `ticker` is chunked+embedded in Postgres.

    Never raises: grounding is best-effort and the pipeline continues without
    filings when EDGAR is down or the ticker isn't a US filer (ADR: Failure Modes).
    """
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            meta = await edgar.latest_filing(client, ticker)

            existing = await db.execute(
                select(Filing).where(Filing.accession_no == meta.accession_no)
            )
            filing = existing.scalar_one_or_none()
            if filing is not None:
                return IngestStatus(
                    status="cached",
                    detail=f"{meta.form_type} filed {meta.filing_date} already ingested",
                    form_type=meta.form_type,
                    filing_date=meta.filing_date,
                    chunk_count=filing.chunk_count,
                )

            text = await edgar.fetch_filing_text(client, meta)

        chunks = chunk_filing(text)
        if not chunks:
            return IngestStatus(status="unavailable", detail="filing parsed to empty text")

        embeddings = await embed_texts([c.content for c in chunks])

        filing = Filing(
            id=uuid.uuid4(),
            ticker=meta.ticker,
            cik=meta.cik,
            form_type=meta.form_type,
            accession_no=meta.accession_no,
            filing_date=meta.filing_date,
            url=meta.url,
            chunk_count=len(chunks),
        )
        db.add(filing)
        db.add_all(
            FilingChunk(
                id=uuid.uuid4(),
                filing_id=filing.id,
                item=chunk.item,
                section_title=chunk.section_title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, embeddings.vectors, strict=True)
        )
        await db.flush()

        return IngestStatus(
            status="ingested",
            detail=f"{meta.form_type} filed {meta.filing_date}: {len(chunks)} chunks embedded",
            form_type=meta.form_type,
            filing_date=meta.filing_date,
            chunk_count=len(chunks),
            embedding_cost_usd=embeddings.cost_usd,
        )

    except edgar.EdgarError as e:
        logger.warning("EDGAR unavailable for %s: %s", ticker, e)
        return IngestStatus(status="unavailable", detail=str(e))
    except Exception as e:  # noqa: BLE001 — grounding must never kill a research run
        logger.exception("Filing ingestion failed for %s", ticker)
        return IngestStatus(status="unavailable", detail=f"ingestion error: {e}")
