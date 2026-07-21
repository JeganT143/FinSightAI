import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.limits import CapacityError, enforce_research_rate_limit, run_gate
from backend.db import crud
from backend.db.models import ResearchReport
from backend.db.session import AsyncSessionLocal, get_db
from backend.pipeline.research import (
    run_research_pipeline,
    run_research_pipeline_stream,
)
from backend.schemas.research import (
    AgentRunDetail,
    ReportDetailResponse,
    ReportListResponse,
    ReportSummary,
    ResearchRequest,
    UsageSummary,
)

router = APIRouter(prefix="/api", tags=["research"])


def _acquire_run_slot() -> None:
    """Claim a concurrency slot or turn the caller away with 503 + Retry-After."""
    try:
        run_gate.acquire()
    except CapacityError as e:
        raise HTTPException(
            status_code=503, detail=str(e), headers={"Retry-After": "60"}
        ) from e


@router.post("/research", dependencies=[Depends(enforce_research_rate_limit)])
async def research(request: ResearchRequest, db: AsyncSession = Depends(get_db)):
    """Non-streaming research run — returns the final `complete` event payload.

    Failures propagate to the middleware error boundary: the client gets a
    clean 500 with an error_id, the log gets the traceback, and the failed
    report row (with full detail) is queryable at /reports/{id}.
    """
    _acquire_run_slot()
    try:
        return await run_research_pipeline(request.ticker, db)
    finally:
        run_gate.release()


@router.post("/research/stream", dependencies=[Depends(enforce_research_rate_limit)])
async def research_stream(request: ResearchRequest):
    """Run the pipeline, streaming SSE events (see ARCHITECTURE.md §6 for the protocol)."""
    _acquire_run_slot()

    async def event_generator():
        # Session is created inside the generator so it lives for the whole stream.
        try:
            async with AsyncSessionLocal() as db:
                try:
                    async for event in run_research_pipeline_stream(request.ticker, db):
                        yield f"data: {json.dumps(event)}\n\n"
                    await db.commit()
                except Exception:
                    # The pipeline already emitted a sanitized `error` event and
                    # persisted the failure; commit the fail_report row and end
                    # the stream cleanly.
                    await db.commit()

            yield "event: done\ndata: {}\n\n"
        finally:
            run_gate.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _summary(report: ResearchReport) -> ReportSummary:
    return ReportSummary(
        id=str(report.id),
        ticker=report.ticker,
        status=report.status,
        verdict=report.verdict,
        overall_score=report.overall_score,
        revision_count=report.revision_count,
        cost_usd=report.cost_usd,
        latency_ms=report.latency_ms,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    ticker: str | None = Query(default=None, max_length=5),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    reports, total = await crud.list_reports(db, ticker=ticker, limit=limit, offset=offset)
    return ReportListResponse(
        reports=[_summary(r) for r in reports], total=total, limit=limit, offset=offset
    )


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    report = await crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportDetailResponse(
        id=str(report.id),
        ticker=report.ticker,
        status=report.status,
        verdict=report.verdict,
        overall_score=report.overall_score,
        report=report.report,
        critic=report.critic,
        revision_count=report.revision_count,
        error=report.error,
        usage=UsageSummary(
            input_tokens=report.prompt_tokens,
            output_tokens=report.completion_tokens,
            cost_usd=report.cost_usd,
            latency_ms=report.latency_ms,
        ),
        agent_runs=[
            AgentRunDetail(
                agent_name=run.agent_name,
                phase=run.phase,
                status=run.status,
                model=run.model,
                output=run.output,
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                cost_usd=run.cost_usd,
                latency_ms=run.latency_ms,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            for run in report.agent_runs
        ],
        created_at=report.created_at,
        completed_at=report.completed_at,
    )
