"""Concierge action tests (SAAS §8.3): tenancy via ContextVar, plan gates.

These exercise the real implementations the @function_tool wrappers call —
no LLM, no Redis; sessions patched onto the shared SQLite fixture.
"""

import uuid

import pytest

from backend.billing.limits import PLAN_LIMITS, check_and_reserve_run
from backend.concierge import actions
from backend.concierge.actions import current_user_id_var
from backend.db.models import User
from tests.test_api import seed_report


@pytest.fixture(autouse=True)
def sqlite_sessions(session_factory, monkeypatch):
    monkeypatch.setattr(actions, "AsyncSessionLocal", session_factory)


@pytest.fixture
async def pro_user(db_session):
    user = User(email="pro@example.com", plan="pro")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
def as_user():
    def _set(user):
        current_user_id_var.set(user.id)

    yield _set
    # Token-based reset would cross async-context boundaries under
    # pytest-asyncio; overwriting with None is equivalent here.
    current_user_id_var.set(None)


async def test_tools_refuse_to_run_outside_a_user_context():
    with pytest.raises(RuntimeError, match="outside a user context"):
        await actions.get_account_status()


async def test_trigger_research_blocked_for_free_plan(db_session, as_user):
    user = User(email="free-chat@example.com", plan="free")
    db_session.add(user)
    await db_session.commit()
    as_user(user)

    result = await actions.trigger_research("NVDA")
    assert result["error"] == "research_runs_require_pro"
    assert "/pricing" in result["message"]


async def test_trigger_research_blocked_over_quota(db_session, pro_user, as_user):
    for _ in range(PLAN_LIMITS["pro"].max_runs_per_period):
        await check_and_reserve_run(db_session, pro_user)
    as_user(pro_user)

    result = await actions.trigger_research("NVDA")
    assert result["error"] == "quota_exceeded"


async def test_trigger_research_starts_background_run(db_session, pro_user, as_user, monkeypatch):
    started: list[tuple] = []

    async def canned_pipeline(ticker, user_id, db, plan_limits=None, existing_report_id=None):
        started.append((ticker, user_id, existing_report_id))
        yield {"type": "complete"}

    monkeypatch.setattr("backend.pipeline.research.run_research_pipeline_stream", canned_pipeline)
    as_user(pro_user)

    result = await actions.trigger_research("nvda")
    assert result["status"] == "started"
    assert result["ticker"] == "NVDA"  # normalized

    # The background task adopts the report row that was created up front.
    import asyncio

    await asyncio.sleep(0.05)
    assert started and started[0][2] == uuid.UUID(result["report_id"])


async def test_get_report_is_tenant_scoped(db_session, pro_user, as_user):
    stranger = User(email="stranger3@example.com", plan="pro")
    db_session.add(stranger)
    await db_session.flush()
    foreign = await seed_report(db_session, stranger.id)
    mine = await seed_report(db_session, pro_user.id, "AAPL")
    await db_session.commit()  # actions read through their own session
    as_user(pro_user)

    assert (await actions.get_report(str(foreign.id)))["error"] == "report not found"
    owned = await actions.get_report(str(mine.id))
    assert owned["ticker"] == "AAPL" and owned["verdict"] == "BUY"
    assert (await actions.get_report("not-a-uuid"))["error"] == "invalid report id"


async def test_search_past_reports_extracts_ticker(db_session, pro_user, as_user):
    await seed_report(db_session, pro_user.id, "NVDA")
    await seed_report(db_session, pro_user.id, "AAPL")
    await db_session.commit()  # actions read through their own session
    as_user(pro_user)

    result = await actions.search_past_reports("what did my NVDA report say?")
    assert result["total"] == 1
    assert result["reports"][0]["ticker"] == "NVDA"

    everything = await actions.search_past_reports("show me everything")
    assert everything["total"] == 2


async def test_get_account_status_reports_plan_and_usage(db_session, pro_user, as_user):
    await check_and_reserve_run(db_session, pro_user)
    as_user(pro_user)

    status = await actions.get_account_status()
    assert status["plan"] == "pro"
    assert status["runs_used"] == 1
    assert status["runs_limit"] == PLAN_LIMITS["pro"].max_runs_per_period
