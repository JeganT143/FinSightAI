"""Deterministic canary routing (SAAS §10.3).

Hash-based, not random: the same user always lands on the same side of the
split, so their experience never flickers between the stable and candidate
model across requests.
"""

import hashlib
import uuid
from dataclasses import replace

from backend.billing.limits import PlanLimit
from backend.core.config import settings


def route_to_canary(user_id: uuid.UUID, canary_percent: int) -> bool:
    """True if this user is inside the canary slice (0-100)."""
    if canary_percent <= 0:
        return False
    if canary_percent >= 100:
        return True
    bucket = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 100
    return bucket < canary_percent


def apply_canary(user_id: uuid.UUID, plan: PlanLimit) -> PlanLimit:
    """Swap in the candidate synthesizer model for canaried users.

    No-op unless SYNTHESIZER_MODEL_CANARY is set and the user hashes into
    the CANARY_PERCENT slice. Free-tier users are never canaried — their
    model tier is a billing promise (SAAS §15), not an experiment surface.
    """
    if not settings.synthesizer_model_canary:
        return plan
    if plan.synthesizer_model != settings.synthesizer_model:
        return plan  # not on the stable pro routing => leave untouched
    if route_to_canary(user_id, settings.canary_percent):
        return replace(plan, synthesizer_model=settings.synthesizer_model_canary)
    return plan
