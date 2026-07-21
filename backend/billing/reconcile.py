"""Webhook-drift correction (SAAS §4.4).

Webhooks are at-least-once but not guaranteed-delivered (an outage window
loses events). This re-fetches ground truth from Stripe for every locally
active subscription and corrects drift. Run on a schedule (cron / Azure
Container Apps job), not on the request path.
"""

import asyncio
import logging
from typing import cast

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.billing.stripe_client import _plan_for_price, _require_stripe
from backend.db.models import Subscription, User

logger = logging.getLogger(__name__)


async def reconcile_subscriptions(db: AsyncSession) -> int:
    """Correct local Subscription/User rows that disagree with Stripe.

    Returns the number of rows corrected.
    """
    _require_stripe()
    corrected = 0
    subs = (
        (
            await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id.is_not(None))
            )
        )
        .scalars()
        .all()
    )

    for sub in subs:
        remote: dict | None
        try:
            resp = await asyncio.to_thread(
                stripe.Subscription.retrieve, str(sub.stripe_subscription_id)
            )
            # StripeObject is a dict subclass at runtime; the stubs don't say so.
            remote = cast(dict, resp)
        except stripe.InvalidRequestError:
            remote = None  # deleted upstream

        if remote is None or remote.get("status") in ("canceled", "unpaid"):
            true_plan, true_status = "free", "canceled"
        else:
            items = remote.get("items", {}).get("data", [])
            price_id = items[0].get("price", {}).get("id") if items else None
            true_plan = _plan_for_price(price_id)
            true_status = "past_due" if remote.get("status") == "past_due" else "active"

        if (sub.plan, sub.status) != (true_plan, true_status):
            logger.warning(
                "reconcile: subscription %s drifted (%s/%s -> %s/%s)",
                sub.id,
                sub.plan,
                sub.status,
                true_plan,
                true_status,
            )
            sub.plan, sub.status = true_plan, true_status
            user = (await db.execute(select(User).where(User.id == sub.user_id))).scalar_one()
            user.plan = true_plan
            corrected += 1

    await db.commit()
    return corrected
