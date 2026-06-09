import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.models import ResearchReport


async def create_report(db: AsyncSession, ticker: str) -> ResearchReport:
    """
    Creates a new report row with status 'running'.
    Called at the START of the pipeline before agents run.
    """
    report = ResearchReport(
        id=uuid.uuid4(),
        ticker=ticker,
        status="running",
        created_at=datetime.utcnow()
    )
    db.add(report)
    await db.flush()
    return report


async def complete_report(
    db: AsyncSession,
    report: ResearchReport,
    report_v1: str,
    report_v2: str | None,
    was_revised: bool,
    fundamentals_output: str,
    risk_output: str,
    sentiment_output: str,
    critic_challenges_found: int,
    critic_assessment: str,
) -> ResearchReport:
    """Updates report row with results after pipeline completes."""
    report.status = "complete"
    report.report_v1 = report_v1
    report.report_v2 = report_v2
    report.was_revised = was_revised
    report.fundamentals_output = fundamentals_output
    report.risk_output = risk_output
    report.sentiment_output = sentiment_output
    report.critic_challenges_found = critic_challenges_found
    report.critic_assessment = critic_assessment
    report.completed_at = datetime.utcnow()
    await db.flush()
    return report


async def fail_report(
    db: AsyncSession,
    report: ResearchReport,
    error: str
) -> ResearchReport:
    """Marks report as failed if pipeline crashes."""
    report.status = "failed"
    report.critic_assessment = f"Pipeline failed: {error}"
    report.completed_at = datetime.utcnow()
    await db.flush()
    return report


async def get_report(
    db: AsyncSession,
    report_id: uuid.UUID
) -> ResearchReport | None:
    """Fetch a single report by ID."""
    result = await db.execute(
        select(ResearchReport).where(ResearchReport.id == report_id)
    )
    return result.scalar_one_or_none()


async def get_reports_by_ticker(
    db: AsyncSession,
    ticker: str,
    limit: int = 10
) -> list[ResearchReport]:
    """Fetch recent reports for a ticker."""
    result = await db.execute(
        select(ResearchReport)
        .where(ResearchReport.ticker == ticker)
        .order_by(ResearchReport.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
