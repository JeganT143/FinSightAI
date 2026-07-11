import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import AgentRun, ResearchReport, utcnow
from backend.pipeline.tracing import TracedRun
from backend.schemas.agents import CriticOutput, ReportDraft


async def create_report(db: AsyncSession, ticker: str) -> ResearchReport:
    """New report row with status 'running', created before agents start."""
    report = ResearchReport(id=uuid.uuid4(), ticker=ticker, status="running")
    db.add(report)
    await db.flush()
    return report


async def add_agent_run(db: AsyncSession, report_id: uuid.UUID, run: TracedRun) -> AgentRun:
    """Persist one agent execution trace (ADR-8)."""
    row = AgentRun(
        id=uuid.uuid4(),
        report_id=report_id,
        agent_name=run.agent_name,
        phase=run.phase,
        status="complete",
        model=run.model,
        output=run.output_dict,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_usd=run.cost_usd,
        latency_ms=run.latency_ms,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )
    db.add(row)
    await db.flush()
    return row


async def complete_report(
    db: AsyncSession,
    report: ResearchReport,
    draft: ReportDraft,
    critic: CriticOutput | None,
    revision_count: int,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: int,
) -> ResearchReport:
    report.status = "complete"
    report.verdict = draft.verdict
    report.overall_score = draft.overall_score
    report.report = draft.model_dump()
    report.critic = critic.model_dump() if critic else None
    report.revision_count = revision_count
    report.prompt_tokens = prompt_tokens
    report.completion_tokens = completion_tokens
    report.cost_usd = round(cost_usd, 6)
    report.latency_ms = latency_ms
    report.completed_at = utcnow()
    await db.flush()
    return report


async def fail_report(db: AsyncSession, report: ResearchReport, error: str) -> ResearchReport:
    report.status = "failed"
    report.error = error
    report.completed_at = utcnow()
    await db.flush()
    return report


async def get_report(db: AsyncSession, report_id: uuid.UUID) -> ResearchReport | None:
    result = await db.execute(
        select(ResearchReport)
        .options(selectinload(ResearchReport.agent_runs))
        .where(ResearchReport.id == report_id)
    )
    return result.scalar_one_or_none()


async def list_reports(
    db: AsyncSession,
    ticker: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ResearchReport], int]:
    """Recent reports (summaries), newest first, with total count for pagination."""
    query = select(ResearchReport)
    count_query = select(func.count(ResearchReport.id))
    if ticker:
        query = query.where(ResearchReport.ticker == ticker.upper())
        count_query = count_query.where(ResearchReport.ticker == ticker.upper())

    total = (await db.execute(count_query)).scalar_one()
    rows = await db.execute(
        query.order_by(ResearchReport.created_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.scalars().all()), total
