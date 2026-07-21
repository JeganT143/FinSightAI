"""Billing routes (SAAS §4): Stripe-hosted Checkout/Portal + the webhook mirror.

The webhook is unauthenticated by design (Stripe calls it) — its auth IS the
signature check. Everything else requires the signed-in user.
"""

import logging
from dataclasses import asdict

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.billing import stripe_client
from backend.billing.limits import PLAN_LIMITS
from backend.billing.stripe_client import BillingNotConfiguredError
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.db.models import User
from backend.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    price_id: str | None = None  # defaults to the Pro price server-side


@router.get("/plans")
async def list_plans() -> dict:
    """Plan metadata for the pricing page (SAAS_DESIGN §3) — the frontend must
    never hardcode numbers PLAN_LIMITS already owns."""
    return {
        "plans": {name: asdict(limit) for name, limit in PLAN_LIMITS.items()},
        "pro_price_id": settings.stripe_price_pro or None,
    }


@router.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    price_id = body.price_id or settings.stripe_price_pro
    # Allowlist: the client may only start checkout for prices we sell.
    if not price_id or price_id != settings.stripe_price_pro:
        raise HTTPException(status_code=400, detail="Unknown price")
    try:
        url = await stripe_client.create_checkout_session(db, user, price_id)
    except BillingNotConfiguredError:
        raise HTTPException(status_code=503, detail="Billing is not configured") from None
    return {"url": url}


@router.post("/portal")
async def portal(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        url = await stripe_client.create_portal_session(db, user)
    except BillingNotConfiguredError:
        raise HTTPException(status_code=503, detail="Billing is not configured") from None
    return {"url": url}


@router.post("/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Verify the Stripe signature, mirror the event locally, 200 fast."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Billing is not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as e:
        logger.warning("webhook rejected: %s", type(e).__name__)
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from None

    action = await stripe_client.apply_webhook_event(db, dict(event))
    logger.info("stripe webhook %s -> %s", event.get("type"), action)
    return {"received": True, "action": action}
