import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.limits import CapacityError, enforce_research_rate_limit, run_gate
from backend.billing.limits import QuotaExceededError, check_and_reserve_run, plan_limits_for
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.db import crud
from backend.db.models import ResearchReport, User
from backend.db.session import AsyncSessionLocal, get_db
from backend.jobs.queue import get_arq_pool
from backend.jobs.stream import job_event_stream
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
        raise HTTPException(status_code=503, detail=str(e), headers={"Retry-After": "60"}) from e


async def _reserve_quota(db: AsyncSession, user: User) -> None:
    """SAAS §6: reserve a run pre-flight; over-quota = 402 + upgrade prompt."""
    try:
        await check_and_reserve_run(db, user)
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=402,
            detail=f"{e} Upgrade at /pricing for a higher limit.",
        ) from e


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def _enqueue_run(db: AsyncSession, user: User, ticker: str) -> ResearchReport:
    """Queued mode (SAAS §7): reserve quota, create the report row, enqueue."""
    await _reserve_quota(db, user)
    report = await crud.create_report(db, user.id, ticker)
    await db.commit()
    pool = await get_arq_pool()
    await pool.enqueue_job("run_research_job", ticker, str(user.id), str(report.id))
    return report


@router.post("/research", dependencies=[Depends(enforce_research_rate_limit)], response_model=None)
async def research(
    request: ResearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict | JSONResponse:
    """Research run entry point.

    Inline mode: runs the pipeline in-request, returns the final `complete`
    payload. Queued mode (SAAS §7): 202 + report_id; events stream from
    GET /api/jobs/{report_id}/stream.
    """
    if settings.queue_enabled:
        report = await _enqueue_run(db, user, request.ticker)
        return JSONResponse(
            status_code=202,
            content={
                "report_id": str(report.id),
                "status": "queued",
                "stream_url": f"/api/jobs/{report.id}/stream",
            },
        )

    # Gate before quota: a 503 (at capacity) must not consume a quota slot.
    _acquire_run_slot()
    try:
        await _reserve_quota(db, user)
        return await run_research_pipeline(request.ticker, user.id, db, plan_limits_for(user))
    finally:
        run_gate.release()


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/research/stream", dependencies=[Depends(enforce_research_rate_limit)])
async def research_stream(
    request: ResearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Run the pipeline, streaming SSE events (see ARCHITECTURE.md §6 for the protocol).

    Same one-call contract in both modes. Queued mode subscribes to the job's
    Redis channel *before* enqueueing (no missed events) and relays; the
    two-step handshake (202 + GET /api/jobs/{id}/stream) also exists for
    clients that want reconnect support.
    """
    if settings.queue_enabled:
        await _reserve_quota(db, user)
        report = await crud.create_report(db, user.id, request.ticker)
        await db.commit()
        report_id, ticker, user_id_str = str(report.id), request.ticker, str(user.id)

        async def enqueue() -> None:
            pool = await get_arq_pool()
            await pool.enqueue_job("run_research_job", ticker, user_id_str, report_id)

        async def queued_generator() -> AsyncGenerator[str]:
            async for event in job_event_stream(report_id, enqueue=enqueue):
                yield _sse(event)
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            queued_generator(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    # ---- inline mode (no Redis; Phase-1 behavior) ----
    # Gate before quota: a 503 (at capacity) must not consume a quota slot.
    _acquire_run_slot()
    try:
        await _reserve_quota(db, user)
    except BaseException:
        run_gate.release()
        raise
    user_id, plan = user.id, plan_limits_for(user)

    async def event_generator() -> AsyncGenerator[str]:
        # Session is created inside the generator so it lives for the whole stream.
        try:
            async with AsyncSessionLocal() as stream_db:
                try:
                    async for event in run_research_pipeline_stream(
                        request.ticker, user_id, stream_db, plan
                    ):
                        yield _sse(event)
                    await stream_db.commit()
                except Exception:
                    # The pipeline already emitted a sanitized `error` event and
                    # persisted the failure; commit the fail_report row and end
                    # the stream cleanly.
                    await stream_db.commit()

            yield "event: done\ndata: {}\n\n"
        finally:
            run_gate.release()

    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.get("/jobs/{report_id}/stream")
async def job_stream(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Reattach to a queued run's event stream (SAAS §7.3).

    Finished runs get a DB snapshot (the terminal event is never lost even
    though pub/sub has no replay); running ones get the live relay.
    """
    if not settings.queue_enabled:
        raise HTTPException(status_code=404, detail="Queued execution is not enabled")
    report = await crud.get_report(db, user.id, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    async def generator() -> AsyncGenerator[str]:
        if report.status == "complete":
            yield _sse(
                {
                    "type": "complete",
                    "report_id": str(report.id),
                    "ticker": report.ticker,
                    "report": report.report,
                    "critic": report.critic,
                    "revision_count": report.revision_count,
                    "usage_summary": {
                        "input_tokens": report.prompt_tokens,
                        "output_tokens": report.completion_tokens,
                        "cost_usd": report.cost_usd,
                        "latency_ms": report.latency_ms,
                    },
                }
            )
        elif report.status == "failed":
            yield _sse(
                {
                    "type": "error",
                    "message": "Research run failed. Full detail is stored on the report.",
                    "report_id": str(report.id),
                }
            )
        else:
            async for event in job_event_stream(str(report.id)):
                yield _sse(event)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportListResponse:
    reports, total = await crud.list_reports(db, user.id, ticker=ticker, limit=limit, offset=offset)
    return ReportListResponse(
        reports=[_summary(r) for r in reports], total=total, limit=limit, offset=offset
    )


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportDetailResponse:
    report = await crud.get_report(db, user.id, report_id)
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
