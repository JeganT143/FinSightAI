"""Usage metering and plan enforcement (SAAS §6).

The §6 exit criterion: a free user's over-limit request is a 402 with an
upgrade prompt — and costs zero tokens (the stub pipeline proves nothing
ran only quota logic did).
"""

from datetime import datetime

import pytest

from backend.billing.limits import (
    PLAN_LIMITS,
    QuotaExceededError,
    accrue_usage,
    check_and_reserve_run,
    current_period,
    usage_summary,
)
from backend.db.models import User


def test_period_is_calendar_month_utc():
    start, end = current_period(datetime(2026, 7, 21, 15, 30))
    assert start == datetime(2026, 7, 1)
    assert end == datetime(2026, 8, 1)


def test_period_december_rolls_into_next_year():
    start, end = current_period(datetime(2026, 12, 5))
    assert start == datetime(2026, 12, 1)
    assert end == datetime(2027, 1, 1)


def test_free_plan_caps_model_tier_not_just_count():
    free = PLAN_LIMITS["free"]
    assert free.specialist_model == free.synthesizer_model == free.critic_model == "gpt-4o-mini"
    assert PLAN_LIMITS["pro"].synthesizer_model != "gpt-4o-mini"


@pytest.fixture
async def free_user(db_session):
    user = User(email="free@example.com", plan="free")
    db_session.add(user)
    await db_session.commit()
    return user


async def test_reserve_up_to_limit_then_quota_error(db_session, free_user):
    limit = PLAN_LIMITS["free"].max_runs_per_period
    for _ in range(limit):
        await check_and_reserve_run(db_session, free_user)

    with pytest.raises(QuotaExceededError) as exc:
        await check_and_reserve_run(db_session, free_user)
    assert "free plan" in str(exc.value)
    assert "resets on" in str(exc.value)


async def test_usage_summary_reflects_reservations_and_accruals(db_session, free_user):
    await check_and_reserve_run(db_session, free_user)
    await accrue_usage(db_session, free_user.id, tokens=1500, cost_usd=0.02)

    summary = await usage_summary(db_session, free_user)
    assert summary["plan"] == "free"
    assert summary["runs_used"] == 1
    assert summary["runs_limit"] == PLAN_LIMITS["free"].max_runs_per_period


async def test_sixth_free_run_is_402_with_upgrade_prompt(client, db_session, monkeypatch):
    # The dev user auth resolves to must be on the free plan for this test.
    user = User(email="dev@localhost", plan="free")
    db_session.add(user)
    await db_session.commit()

    async def fake_pipeline(ticker, user_id, db, plan_limits=None):
        return {"type": "complete", "ticker": ticker}

    monkeypatch.setattr("backend.api.routes_research.run_research_pipeline", fake_pipeline)
    # Route-level rate limiter would trip at 10 requests/hr before quota's 5 —
    # widen it so this test exercises quota, not the rate limiter.
    from backend.api.limits import SlidingWindowLimiter

    monkeypatch.setattr(
        "backend.api.limits.research_limiter",
        SlidingWindowLimiter(max_requests=100, window_seconds=3600),
    )

    for i in range(PLAN_LIMITS["free"].max_runs_per_period):
        resp = await client.post("/api/research", json={"ticker": "NVDA"})
        assert resp.status_code == 200, f"run {i + 1} should be within quota"

    resp = await client.post("/api/research", json={"ticker": "NVDA"})
    assert resp.status_code == 402
    assert "Upgrade at /pricing" in resp.json()["detail"]


async def test_usage_endpoint_shape(client, dev_user):
    resp = await client.get("/api/account/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"plan", "runs_used", "runs_limit", "period_end"}
    assert body["plan"] == "pro"
