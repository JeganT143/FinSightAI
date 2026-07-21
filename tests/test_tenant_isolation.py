"""Tenant isolation (SAAS §5) — the exit criterion for Phase 2a.

Backend-only, testable guarantee: user A can never see user B's reports,
and an off-tenant lookup is indistinguishable from a missing row.
"""

from backend.db import crud
from backend.db.models import User
from tests.test_api import seed_report


async def _two_users(db):
    a = User(email="a@example.com", external_auth_id="user_a", plan="pro")
    b = User(email="b@example.com", external_auth_id="user_b", plan="free")
    db.add_all([a, b])
    await db.commit()
    return a, b


async def test_list_reports_is_user_scoped(db_session):
    a, b = await _two_users(db_session)
    await seed_report(db_session, a.id, "NVDA")
    await seed_report(db_session, b.id, "AAPL")

    a_reports, a_total = await crud.list_reports(db_session, a.id)
    assert a_total == 1
    assert all(r.user_id == a.id for r in a_reports)
    assert [r.ticker for r in a_reports] == ["NVDA"]


async def test_get_report_denies_other_tenant_indistinguishably(db_session):
    a, b = await _two_users(db_session)
    b_report = await seed_report(db_session, b.id, "AAPL")

    # A's view of B's report is None — exactly like a nonexistent id, so the
    # status code (404) can't be used to probe which report ids exist.
    assert await crud.get_report(db_session, a.id, b_report.id) is None
    owned = await crud.get_report(db_session, b.id, b_report.id)
    assert owned is not None and owned.id == b_report.id


async def test_ticker_filter_cannot_cross_tenants(db_session):
    a, b = await _two_users(db_session)
    await seed_report(db_session, b.id, "NVDA")

    _, total = await crud.list_reports(db_session, a.id, ticker="NVDA")
    assert total == 0
