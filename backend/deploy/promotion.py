"""Canary promotion decision (SAAS §10.4).

Pulls real canary runs from agent_runs, judges a sample with the Tier-2
judge, and compares against the stable model's recent average. The output
informs a human-triggered config change (flip CANARY_PERCENT) — deliberately
not auto-promotion at this team size.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.models import AgentRun, ResearchReport
from evals.judges import judge_report

logger = logging.getLogger(__name__)

_SAMPLE_LIMIT = 10  # judge cost is real money; a directional read needs ~10


@dataclass
class PromotionDecision:
    promote: bool
    sample_size: int
    avg_score: float
    baseline_score: float
    detail: str


async def _judge_model_sample(db: AsyncSession, model: str, since: datetime) -> tuple[float, int]:
    """Average judge score over completed synthesis runs for `model`."""
    rows = (
        await db.execute(
            select(AgentRun, ResearchReport)
            .join(ResearchReport, AgentRun.report_id == ResearchReport.id)
            .where(
                AgentRun.model == model,
                AgentRun.phase.in_(("synthesis", "revision")),
                AgentRun.started_at >= since,
                ResearchReport.status == "complete",
            )
            .order_by(AgentRun.started_at.desc())
            .limit(_SAMPLE_LIMIT)
        )
    ).all()
    if not rows:
        return 0.0, 0

    total = 0.0
    judged = 0
    for _run, report in rows:
        if not report.report:
            continue
        scores = await judge_report(specialists={}, report=report.report)
        total += (scores.groundedness + scores.completeness + scores.actionability) / 3
        judged += 1
    return (total / judged if judged else 0.0), judged


async def evaluate_canary_promotion(db: AsyncSession, since: datetime) -> PromotionDecision:
    if not settings.synthesizer_model_canary:
        return PromotionDecision(False, 0, 0.0, 0.0, "no canary model configured")

    canary_avg, canary_n = await _judge_model_sample(db, settings.synthesizer_model_canary, since)
    stable_avg, stable_n = await _judge_model_sample(db, settings.synthesizer_model, since)

    if canary_n < 5:
        return PromotionDecision(
            False, canary_n, canary_avg, stable_avg, f"insufficient canary sample ({canary_n} < 5)"
        )

    promote = canary_avg >= stable_avg - 0.1  # candidate must not regress quality
    detail = (
        f"canary {settings.synthesizer_model_canary} avg={canary_avg:.2f} (n={canary_n}) vs "
        f"stable {settings.synthesizer_model} avg={stable_avg:.2f} (n={stable_n})"
    )
    logger.info("canary promotion decision: promote=%s — %s", promote, detail)
    return PromotionDecision(promote, canary_n, canary_avg, stable_avg, detail)
