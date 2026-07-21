"""Concierge tools (SAAS §8.3).

Tenancy rule: every tool reads the current user's id from a per-request
ContextVar — NEVER as a model-supplied argument — so the model cannot
address another tenant's data even if prompted to. Each tool opens its own
session (tools run inside an agent's concurrent execution).
"""

import logging
import uuid
from contextvars import ContextVar

from agents import function_tool

from backend.billing.limits import (
    QuotaExceededError,
    check_and_reserve_run,
    plan_limits_for,
    usage_summary,
)
from backend.core.config import settings
from backend.db import crud
from backend.db.models import User
from backend.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

current_user_id_var: ContextVar[uuid.UUID | None] = ContextVar("concierge_user_id", default=None)


def _require_user_id() -> uuid.UUID:
    user_id = current_user_id_var.get()
    if user_id is None:
        raise RuntimeError("concierge tool called outside a user context")
    return user_id


@function_tool
async def trigger_research(ticker: str) -> dict:
    """Start a full research run for a stock ticker. Returns the report_id the
    user can watch. Use ONLY when the user asks to research/analyze a ticker
    and no recent report exists (check search_past_reports first).

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    user_id = _require_user_id()
    ticker = ticker.upper().strip()
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            return {"error": "account not found"}
        if user.plan == "free":
            # SAAS §15: free-tier chat is Q&A only.
            return {
                "error": "research_runs_require_pro",
                "message": "Starting research runs from chat is a Pro feature. "
                "The user can run research from the Console, or upgrade at /pricing.",
            }
        try:
            await check_and_reserve_run(db, user)
        except QuotaExceededError as e:
            return {"error": "quota_exceeded", "message": str(e)}

        report = await crud.create_report(db, user_id, ticker)
        await db.commit()
        report_id = str(report.id)

    if settings.queue_enabled:
        from backend.jobs.queue import get_arq_pool

        pool = await get_arq_pool()
        await pool.enqueue_job("run_research_job", ticker, str(user_id), report_id)
    else:
        # Inline mode: run in the background so the chat turn returns now.
        import asyncio

        from backend.billing.limits import PLAN_LIMITS
        from backend.pipeline.research import run_research_pipeline_stream

        async def _background_run() -> None:
            async with AsyncSessionLocal() as run_db:
                try:
                    async for _ in run_research_pipeline_stream(
                        ticker,
                        user_id,
                        run_db,
                        PLAN_LIMITS.get("pro"),
                        existing_report_id=uuid.UUID(report_id),
                    ):
                        pass
                    await run_db.commit()
                except Exception:
                    await run_db.commit()
                    logger.exception("background research run failed: %s", report_id)

        asyncio.create_task(_background_run())

    return {
        "report_id": report_id,
        "ticker": ticker,
        "status": "started",
        "note": "Tell the user research has started and link the report id.",
    }


@function_tool
async def get_report(report_id: str) -> dict:
    """Fetch one of the user's research reports by id (full structured report).

    Args:
        report_id: The report's UUID
    """
    user_id = _require_user_id()
    try:
        rid = uuid.UUID(report_id)
    except ValueError:
        return {"error": "invalid report id"}
    async with AsyncSessionLocal() as db:
        report = await crud.get_report(db, user_id, rid)
    if report is None:
        return {"error": "report not found"}
    return {
        "report_id": str(report.id),
        "ticker": report.ticker,
        "status": report.status,
        "verdict": report.verdict,
        "overall_score": report.overall_score,
        "report": report.report,
        "critic": report.critic,
    }


@function_tool
async def search_past_reports(query: str) -> dict:
    """List the user's recent reports, optionally narrowed by a ticker symbol
    found in the query. Use before trigger_research to avoid duplicate runs.

    Args:
        query: Free text; a ticker symbol in it (e.g. 'NVDA') narrows results
    """
    user_id = _require_user_id()
    ticker = None
    for token in query.upper().replace("$", " ").split():
        if token.isalpha() and 1 <= len(token) <= 5 and token not in ("THE", "MY", "FOR", "ON"):
            ticker = token
            break
    async with AsyncSessionLocal() as db:
        reports, total = await crud.list_reports(db, user_id, ticker=ticker, limit=10)
    return {
        "total": total,
        "reports": [
            {
                "report_id": str(r.id),
                "ticker": r.ticker,
                "status": r.status,
                "verdict": r.verdict,
                "overall_score": r.overall_score,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
    }


@function_tool
async def get_account_status() -> dict:
    """The user's plan and current-period usage (runs used / limit)."""
    user_id = _require_user_id()
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            return {"error": "account not found"}
        summary = await usage_summary(db, user)
    summary["models"] = plan_limits_for(user).synthesizer_model
    return summary
