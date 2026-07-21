"""Billing reconciliation (SAAS §4.4) and canary promotion (§10.4) tests —
Stripe and the LLM judge are faked; the drift/decision logic is real."""

from datetime import datetime, timedelta

import pytest
import stripe
from sqlalchemy import select

from backend.billing import reconcile as reconcile_module
from backend.billing.reconcile import reconcile_subscriptions
from backend.core.config import settings
from backend.db.models import Subscription, User
from backend.deploy.promotion import evaluate_canary_promotion


@pytest.fixture(autouse=True)
def stripe_configured(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_test_123")


async def _pro_subscriber(db, sub_id="sub_1"):
    user = User(email=f"{sub_id}@example.com", plan="pro")
    db.add(user)
    await db.flush()
    sub = Subscription(
        user_id=user.id,
        stripe_customer_id="cus_1",
        stripe_subscription_id=sub_id,
        plan="pro",
        status="active",
    )
    db.add(sub)
    await db.commit()
    return user, sub


async def test_reconcile_corrects_upstream_cancellation(db_session, monkeypatch):
    user, _ = await _pro_subscriber(db_session)

    def fake_retrieve(sub_id):
        return {"status": "canceled", "items": {"data": []}}

    monkeypatch.setattr(reconcile_module.stripe.Subscription, "retrieve", fake_retrieve)

    corrected = await reconcile_subscriptions(db_session)
    assert corrected == 1

    refreshed = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.plan == "free"


async def test_reconcile_handles_deleted_subscription(db_session, monkeypatch):
    await _pro_subscriber(db_session, "sub_gone")

    def exploding_retrieve(sub_id):
        raise stripe.InvalidRequestError("No such subscription", param=None)

    monkeypatch.setattr(reconcile_module.stripe.Subscription, "retrieve", exploding_retrieve)
    assert await reconcile_subscriptions(db_session) == 1


async def test_reconcile_leaves_agreeing_rows_alone(db_session, monkeypatch):
    await _pro_subscriber(db_session, "sub_ok")

    def fake_retrieve(sub_id):
        return {
            "status": "active",
            "items": {"data": [{"price": {"id": settings.stripe_price_pro}}]},
        }

    monkeypatch.setattr(reconcile_module.stripe.Subscription, "retrieve", fake_retrieve)
    assert await reconcile_subscriptions(db_session) == 0


async def test_promotion_requires_a_canary_model(db_session):
    decision = await evaluate_canary_promotion(db_session, datetime.now() - timedelta(days=1))
    assert decision.promote is False
    assert "no canary model" in decision.detail


async def test_promotion_refuses_thin_samples(db_session, monkeypatch):
    monkeypatch.setattr(settings, "synthesizer_model_canary", "gpt-5-mini")
    # No canary runs exist at all -> sample of 0 -> never promote on noise.
    decision = await evaluate_canary_promotion(db_session, datetime.now() - timedelta(days=1))
    assert decision.promote is False
    assert decision.sample_size == 0
    assert "insufficient" in decision.detail
