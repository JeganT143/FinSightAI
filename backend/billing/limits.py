"""Plan limits + usage metering (SAAS §6).

Quota is *reserved* pre-flight — before a run is enqueued or executed — never
counted after the fact: a free-tier user's over-limit request must cost zero
tokens. The free tier caps the model tier too (SAAS §15), bounding worst-case
free cost independently of the run count.

Periods are calendar months (UTC). Aligning paid users' periods to their
Stripe billing anchor is a deliberate simplification to revisit — noted in
SAAS_ARCHITECTURE.md §6.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.models import UsageCounter, User


@dataclass(frozen=True)
class PlanLimit:
    max_runs_per_period: int
    specialist_model: str
    synthesizer_model: str
    critic_model: str


PLAN_LIMITS: dict[str, PlanLimit] = {
    # Free: cheapest model everywhere — bounds worst-case cost per run.
    "free": PlanLimit(5, "gpt-4o-mini", "gpt-4o-mini", "gpt-4o-mini"),
    # Pro: the full ADR-4 routing (reads the same settings the Phase-1 pipeline used).
    "pro": PlanLimit(
        100,
        settings.specialist_model,
        settings.synthesizer_model,
        settings.critic_model,
    ),
}


def plan_limits_for(user: User) -> PlanLimit:
    return PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])


class QuotaExceededError(Exception):
    def __init__(self, plan: str, limit: int, period_end: datetime) -> None:
        self.plan = plan
        self.limit = limit
        self.period_end = period_end
        super().__init__(
            f"The {plan} plan includes {limit} research runs per month; "
            f"the limit resets on {period_end.date().isoformat()}."
        )


def current_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Calendar-month period boundaries (UTC, naive — matches DB convention)."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, end


async def _locked_counter(
    db: AsyncSession, user_id: uuid.UUID, start: datetime, end: datetime
) -> UsageCounter:
    """The current period's counter row, row-locked; created if absent.

    Concurrent first-requests race on the insert; the unique (user_id,
    period_start) index makes the loser fail, roll back, and re-select the
    winner's row. Runs before any other write in the request, so the
    rollback discards nothing else.
    """
    stmt = (
        select(UsageCounter)
        .where(UsageCounter.user_id == user_id, UsageCounter.period_start == start)
        .with_for_update()
    )
    counter = (await db.execute(stmt)).scalar_one_or_none()
    if counter is not None:
        return counter

    try:
        counter = UsageCounter(user_id=user_id, period_start=start, period_end=end)
        db.add(counter)
        await db.flush()
        return counter
    except IntegrityError:
        await db.rollback()
        return (await db.execute(stmt)).scalar_one()


async def check_and_reserve_run(db: AsyncSession, user: User) -> None:
    """Reserve one run from the user's quota or raise QuotaExceededError.

    Commits on success so the reservation survives a crash later in the
    request (a failed run still consumed the slot — refunds are a product
    decision, not an accounting accident).
    """
    limits = plan_limits_for(user)
    start, end = current_period()
    counter = await _locked_counter(db, user.id, start, end)

    if counter.research_runs_used >= limits.max_runs_per_period:
        raise QuotaExceededError(user.plan, limits.max_runs_per_period, counter.period_end)

    counter.research_runs_used += 1
    await db.commit()


async def accrue_usage(db: AsyncSession, user_id: uuid.UUID, tokens: int, cost_usd: float) -> None:
    """Record actuals after a run completes (additive UPDATE, no lock needed)."""
    start, _ = current_period()
    await db.execute(
        update(UsageCounter)
        .where(UsageCounter.user_id == user_id, UsageCounter.period_start == start)
        .values(
            tokens_used=UsageCounter.tokens_used + tokens,
            cost_usd_accrued=UsageCounter.cost_usd_accrued + cost_usd,
        )
    )


async def usage_summary(db: AsyncSession, user: User) -> dict:
    """The /api/account/usage payload (SAAS §6.4)."""
    limits = plan_limits_for(user)
    start, end = current_period()
    counter = (
        await db.execute(
            select(UsageCounter).where(
                UsageCounter.user_id == user.id, UsageCounter.period_start == start
            )
        )
    ).scalar_one_or_none()
    return {
        "plan": user.plan,
        "runs_used": counter.research_runs_used if counter else 0,
        "runs_limit": limits.max_runs_per_period,
        "period_end": end.isoformat(),
    }
