import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.config import settings
from backend.db.session import Base

# JSONB on Postgres, plain JSON elsewhere (lets unit tests run on SQLite).
JsonB = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reports: Mapped[list["ResearchReport"]] = relationship(back_populates="user")


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|complete|failed

    # Final structured report (serialized ReportDraft) — the UI renders from this.
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report: Mapped[dict | None] = mapped_column(JsonB, nullable=True)

    # Adversarial review trail
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    critic: Mapped[dict | None] = mapped_column(JsonB, nullable=True)  # final CriticOutput

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Run totals (per-agent detail lives in agent_runs)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="reports")
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="AgentRun.started_at"
    )


class AgentRun(Base):
    """One agent execution within a pipeline run — the observability unit (ADR-8)."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_reports.id", ondelete="CASCADE"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False)  # research|synthesis|critique|revision
    status: Mapped[str] = mapped_column(String(20), default="complete")  # complete|failed
    model: Mapped[str] = mapped_column(String(50), nullable=False)

    output: Mapped[dict | None] = mapped_column(JsonB, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    report: Mapped["ResearchReport"] = relationship(back_populates="agent_runs")


class Filing(Base):
    """An ingested SEC filing (ADR-5). One row per accession number."""

    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    cik: Mapped[str] = mapped_column(String(10), nullable=False)
    form_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 10-K | 10-Q
    accession_no: Mapped[str] = mapped_column(String(25), unique=True, nullable=False)
    filing_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    url: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    chunks: Mapped[list["FilingChunk"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )


class FilingChunk(Base):
    """Section-aware chunk of a filing with its embedding (pgvector)."""

    __tablename__ = "filing_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"), index=True
    )
    item: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "1A", "7"
    section_title: Mapped[str] = mapped_column(String(120), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dimensions), nullable=True)

    filing: Mapped["Filing"] = relationship(back_populates="chunks")

    __table_args__ = (
        # HNSW index for cosine ANN search — created here so tests on Postgres get it;
        # postgresql_using is ignored by other dialects only if the table is skipped there.
        Index(
            "ix_filing_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
