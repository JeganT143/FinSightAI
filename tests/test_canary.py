"""Canary routing tests (SAAS §10.3): determinism and the guardrails."""

import uuid

from backend.billing.limits import PLAN_LIMITS
from backend.core.config import settings
from backend.deploy.canary import apply_canary, route_to_canary


def test_same_user_always_lands_on_same_side():
    user_id = uuid.uuid4()
    results = {route_to_canary(user_id, 50) for _ in range(20)}
    assert len(results) == 1  # never flickers


def test_slice_boundaries():
    user_id = uuid.uuid4()
    assert route_to_canary(user_id, 0) is False
    assert route_to_canary(user_id, 100) is True


def test_split_is_roughly_proportional():
    hits = sum(route_to_canary(uuid.uuid4(), 30) for _ in range(2000))
    assert 450 < hits < 750  # 30% ± tolerance over 2000 users


def test_apply_canary_swaps_only_synthesizer(monkeypatch):
    monkeypatch.setattr(settings, "synthesizer_model_canary", "gpt-5-mini")
    monkeypatch.setattr(settings, "canary_percent", 100)

    plan = apply_canary(uuid.uuid4(), PLAN_LIMITS["pro"])
    assert plan.synthesizer_model == "gpt-5-mini"
    assert plan.specialist_model == PLAN_LIMITS["pro"].specialist_model
    assert plan.critic_model == PLAN_LIMITS["pro"].critic_model


def test_free_tier_is_never_canaried(monkeypatch):
    monkeypatch.setattr(settings, "synthesizer_model_canary", "gpt-5-mini")
    monkeypatch.setattr(settings, "canary_percent", 100)

    plan = apply_canary(uuid.uuid4(), PLAN_LIMITS["free"])
    assert plan == PLAN_LIMITS["free"]  # billing promise, not experiment surface


def test_no_canary_configured_is_a_noop():
    assert apply_canary(uuid.uuid4(), PLAN_LIMITS["pro"]) == PLAN_LIMITS["pro"]
