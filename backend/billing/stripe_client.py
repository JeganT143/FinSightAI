"""Stripe integration (SAAS §4). Stripe is the system of record; this module
never sees card data — Checkout and the Customer Portal are Stripe-hosted.

The stripe SDK is sync; calls are pushed to a thread so the event loop never
blocks on Stripe's API latency.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.models import Subscription, User

logger = logging.getLogger(__name__)


class BillingNotConfiguredError(Exception):
    """Raised when Stripe keys are absent — billing routes surface this as 503."""


def _require_stripe() -> None:
    if not settings.stripe_secret_key:
        raise BillingNotConfiguredError("STRIPE_SECRET_KEY is not set")
    stripe.api_key = settings.stripe_secret_key


async def _get_or_create_subscription_row(db: AsyncSession, user: User) -> Subscription:
    sub = (
        await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, plan=user.plan)
        db.add(sub)
        await db.flush()
    return sub


async def _ensure_stripe_customer(db: AsyncSession, user: User) -> str:
    """The user's Stripe customer id, creating the customer on first use."""
    sub = await _get_or_create_subscription_row(db, user)
    if sub.stripe_customer_id:
        return sub.stripe_customer_id

    customer = await asyncio.to_thread(
        stripe.Customer.create, email=user.email, metadata={"user_id": str(user.id)}
    )
    sub.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


async def create_checkout_session(db: AsyncSession, user: User, price_id: str) -> str:
    """A Stripe-hosted Checkout URL for a subscription to `price_id`."""
    _require_stripe()
    customer_id = await _ensure_stripe_customer(db, user)
    session = await asyncio.to_thread(
        stripe.checkout.Session.create,
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        # Webhook-side mapping back to our user, independent of customer id.
        client_reference_id=str(user.id),
    )
    if not session.url:
        raise RuntimeError("Stripe returned a checkout session without a URL")
    return session.url


async def create_portal_session(db: AsyncSession, user: User) -> str:
    """A Stripe-hosted Customer Portal URL (manage payment method, cancel, invoices)."""
    _require_stripe()
    customer_id = await _ensure_stripe_customer(db, user)
    portal = await asyncio.to_thread(
        stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=settings.billing_success_url,
    )
    return portal.url


def _plan_for_price(price_id: str | None) -> str:
    return "pro" if price_id and price_id == settings.stripe_price_pro else "free"


async def apply_webhook_event(db: AsyncSession, event: dict) -> str:
    """Upsert local state from a verified Stripe event. Returns the action taken.

    Kept fast (Stripe requires a quick 200): single-row updates, no external
    calls. Anything heavier belongs in reconcile.py.
    """
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    async def _user_for_customer(customer_id: str | None) -> tuple[User, Subscription] | None:
        if not customer_id:
            return None
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.stripe_customer_id == customer_id)
            )
        ).scalar_one_or_none()
        if sub is None:
            return None
        user = (await db.execute(select(User).where(User.id == sub.user_id))).scalar_one()
        return user, sub

    match event_type:
        case "checkout.session.completed":
            # Prefer our own reference; fall back to the customer mapping.
            found = None
            if obj.get("client_reference_id"):
                user = (
                    await db.execute(
                        select(User).where(User.id == uuid.UUID(obj["client_reference_id"]))
                    )
                ).scalar_one_or_none()
                if user:
                    found = (user, await _get_or_create_subscription_row(db, user))
            if found is None:
                found = await _user_for_customer(obj.get("customer"))
            if found is None:
                logger.warning(
                    "checkout.session.completed for unknown customer %s", obj.get("customer")
                )
                return "ignored:unknown-customer"
            user, sub = found
            sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
            sub.stripe_subscription_id = obj.get("subscription")
            sub.plan = "pro"
            sub.status = "active"
            user.plan = "pro"
            await db.commit()
            return "upgraded:pro"

        case "customer.subscription.updated" | "customer.subscription.deleted":
            found = await _user_for_customer(obj.get("customer"))
            if found is None:
                return "ignored:unknown-customer"
            user, sub = found
            status = obj.get("status", "canceled")
            deleted = event_type.endswith("deleted") or status in ("canceled", "unpaid")
            items = obj.get("items", {}).get("data", [])
            price_id = items[0].get("price", {}).get("id") if items else None
            period_end = obj.get("current_period_end")
            sub.stripe_subscription_id = obj.get("id", sub.stripe_subscription_id)
            sub.status = (
                "canceled" if deleted else ("past_due" if status == "past_due" else "active")
            )
            sub.plan = "free" if deleted else _plan_for_price(price_id)
            sub.current_period_end = (
                datetime.fromtimestamp(period_end, UTC).replace(tzinfo=None) if period_end else None
            )
            user.plan = sub.plan
            await db.commit()
            return f"synced:{sub.plan}:{sub.status}"

        case "invoice.payment_failed":
            found = await _user_for_customer(obj.get("customer"))
            if found is None:
                return "ignored:unknown-customer"
            _, sub = found
            sub.status = "past_due"  # plan unchanged: dunning, not cancellation
            await db.commit()
            return "marked:past_due"

        case _:
            return f"ignored:{event_type}"
