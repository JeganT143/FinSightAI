"""Concierge tool implementations (SAAS §8.3) — plain async functions.

Separated from the @function_tool wrappers (backend/tools/concierge_tools.py)
so the tenancy and plan logic is directly unit-testable; the wrappers add
only the LLM-facing docstrings.

Tenancy rule: every action reads the current user's id from a per-request
ContextVar — NEVER as a model-supplied argument — so the model cannot
address another tenant's data even if prompted to. Each action opens its own
session (tools run inside an agent's concurrent execution).
"""

import asyncio
import logging
import uuid
from contextvars import ContextVar

from backend.billing.limits import (
    PLAN_LIMITS,
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


async def trigger_research(ticker: str) -> dict:
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

        asyncio.create_task(_background_run())  # noqa: RUF006 — fire-and-forget by design

    return {
        "report_id": report_id,
        "ticker": ticker,
        "status": "started",
        "note": "Tell the user research has started and link the report id.",
    }


async def get_report(report_id: str) -> dict:
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


def _extract_ticker(query: str) -> str | None:
    """A ticker is a word the USER already wrote as one: ALL-CAPS 1-5 letters
    ("my NVDA report") or $-prefixed in any case ("$nvda"). Ordinary words
    never qualify, so "what did my report say" finds nothing."""
    for raw in query.split():
        dollar = raw.startswith("$")
        token = raw.strip(".,!?()").lstrip("$")
        if not (token.isalpha() and 1 <= len(token) <= 5):
            continue
        if dollar or (token.isupper() and token not in ("I", "A")):
            return token.upper()
    return None


async def search_past_reports(query: str) -> dict:
    user_id = _require_user_id()
    ticker = _extract_ticker(query)
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


async def get_account_status() -> dict:
    user_id = _require_user_id()
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            return {"error": "account not found"}
        summary = await usage_summary(db, user)
    summary["models"] = plan_limits_for(user).synthesizer_model
    return summary
