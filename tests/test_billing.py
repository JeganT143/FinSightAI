"""Billing tests (SAAS §4): webhook state transitions and route guards.

Stripe's API is never called — construct_event is monkeypatched to return
crafted events, and apply_webhook_event's DB effects are asserted directly.
The live round-trip (Checkout -> stripe listen -> webhook) is the §4 manual
verify step, not a unit concern.
"""

import pytest
from sqlalchemy import select

from backend.billing.stripe_client import apply_webhook_event
from backend.core.config import settings
from backend.db.models import Subscription, User

PRO_PRICE = "price_pro_test_123"


@pytest.fixture
async def customer(db_session):
    """A user with a Subscription row already linked to a Stripe customer."""
    user = User(email="payer@example.com", plan="free")
    db_session.add(user)
    await db_session.flush()
    sub = Subscription(user_id=user.id, stripe_customer_id="cus_123", plan="free")
    db_session.add(sub)
    await db_session.commit()
    return user, sub


@pytest.fixture(autouse=True)
def pro_price(monkeypatch):
    monkeypatch.setattr(settings, "stripe_price_pro", PRO_PRICE)


async def test_checkout_completed_upgrades_to_pro(db_session, customer):
    user, _ = customer
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(user.id),
                "customer": "cus_123",
                "subscription": "sub_stripe_1",
            }
        },
    }
    action = await apply_webhook_event(db_session, event)
    assert action == "upgraded:pro"

    refreshed = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.plan == "pro"
    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalar_one()
    assert sub.plan == "pro" and sub.status == "active"
    assert sub.stripe_subscription_id == "sub_stripe_1"


async def test_subscription_deleted_downgrades_to_free(db_session, customer):
    user, sub = customer
    sub.plan, sub.status = "pro", "active"
    user.plan = "pro"
    await db_session.commit()

    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_123", "id": "sub_stripe_1", "status": "canceled"}},
    }
    action = await apply_webhook_event(db_session, event)
    assert action == "synced:free:canceled"

    refreshed = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.plan == "free"


async def test_payment_failed_marks_past_due_without_downgrade(db_session, customer):
    user, sub = customer
    sub.plan, sub.status = "pro", "active"
    user.plan = "pro"
    await db_session.commit()

    event = {"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_123"}}}
    action = await apply_webhook_event(db_session, event)
    assert action == "marked:past_due"

    refreshed_sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalar_one()
    assert refreshed_sub.status == "past_due"
    assert refreshed_sub.plan == "pro"  # dunning, not cancellation
    refreshed = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.plan == "pro"


async def test_unknown_customer_is_ignored_not_500(db_session):
    event = {"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_nobody"}}}
    assert await apply_webhook_event(db_session, event) == "ignored:unknown-customer"


async def test_plans_endpoint_mirrors_plan_limits(client):
    resp = await client.get("/api/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()["plans"]
    assert plans["free"]["max_runs_per_period"] == 5
    assert plans["pro"]["max_runs_per_period"] == 100
    assert plans["free"]["synthesizer_model"] == "gpt-4o-mini"


async def test_checkout_rejects_unknown_price(client, dev_user):
    resp = await client.post("/api/billing/checkout", json={"price_id": "price_evil"})
    assert resp.status_code == 400


async def test_checkout_503_when_unconfigured(client, dev_user, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    resp = await client.post("/api/billing/checkout", json={"price_id": PRO_PRICE})
    assert resp.status_code == 503


async def test_webhook_503_when_unconfigured(client):
    resp = await client.post("/api/billing/webhook", content=b"{}")
    assert resp.status_code == 503


async def test_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    resp = await client.post(
        "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"}
    )
    assert resp.status_code == 400
