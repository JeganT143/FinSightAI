"""Vector retrieval over ingested filing chunks (pgvector cosine ANN)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.models import Filing, FilingChunk
from backend.rag.embeddings import embed_query


@dataclass
class RetrievedChunk:
    content: str
    item: str
    section_title: str
    form_type: str
    filing_date: str
    similarity: float

    @property
    def source(self) -> str:
        return f"{self.form_type} {self.filing_date} Item {self.item} — {self.section_title}"


async def search_chunks(
    db: AsyncSession, ticker: str, query: str, k: int | None = None
) -> list[RetrievedChunk]:
    k = k or settings.rag_top_k
    query_vector = await embed_query(query)

    distance = FilingChunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(FilingChunk, Filing, distance.label("distance"))
        .join(Filing, FilingChunk.filing_id == Filing.id)
        .where(Filing.ticker == ticker.upper())
        .order_by(distance)
        .limit(k)
    )
    rows = (await db.execute(stmt)).all()

    return [
        RetrievedChunk(
            content=chunk.content,
            item=chunk.item,
            section_title=chunk.section_title,
            form_type=filing.form_type,
            filing_date=filing.filing_date,
            similarity=round(1 - dist, 4),
        )
        for chunk, filing, dist in rows
    ]
