"""The queued research job (SAAS §7.2): the unchanged pipeline generator,
with `yield` swapped for Redis pub/sub so any API instance can relay events.

Failure semantics:
- Pipeline errors are persisted by the pipeline itself (fail_report) and NOT
  re-raised to Arq — retrying a deterministic failure only burns tokens.
- Worker death mid-run leaves the job unacked; Arq re-runs it. The re-run
  adopts the same report row (existing_report_id), so the client's report id
  stays valid. Duplicate agent_runs from the dead attempt are possible and
  acceptable — traces are additive, and the final complete_report wins.
"""

import json
import logging
import uuid
from typing import Any

from backend.billing.limits import plan_limits_for
from backend.db.models import User
from backend.db.session import AsyncSessionLocal
from backend.pipeline.research import run_research_pipeline_stream

logger = logging.getLogger(__name__)

STREAM_END = {"type": "stream_end"}


def job_channel(report_id: str) -> str:
    return f"job:{report_id}"


async def run_research_job(ctx: dict[str, Any], ticker: str, user_id: str, report_id: str) -> None:
    redis = ctx["redis"]
    channel = job_channel(report_id)

    async def publish(event: dict) -> None:
        await redis.publish(channel, json.dumps(event))

    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(user_id))
        plan = plan_limits_for(user) if user else None
        try:
            async for event in run_research_pipeline_stream(
                ticker,
                uuid.UUID(user_id),
                db,
                plan,
                existing_report_id=uuid.UUID(report_id),
            ):
                await publish(event)
            await db.commit()
        except Exception:
            # fail_report is already flushed by the pipeline; keep it.
            await db.commit()
            logger.exception("queued run failed: report=%s ticker=%s", report_id, ticker)
        finally:
            await publish(STREAM_END)
