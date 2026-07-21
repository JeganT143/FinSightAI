"""Operational hardening tests (ADR-12): request IDs, error boundary,
rate limiting, concurrency gate, agent timeouts, readiness probe.

Same discipline as the rest of the unit tier: zero LLM calls, zero network,
SQLite via the shared `client` fixture.
"""

import asyncio
import types

import pytest

from backend.api.limits import CapacityError, RunGate, SlidingWindowLimiter
from backend.pipeline.tracing import AgentTimeoutError, traced_run

# ---------------------------------------------------------------------------
# Request context middleware
# ---------------------------------------------------------------------------


async def test_response_carries_generated_request_id(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert len(resp.headers["x-request-id"]) == 12


async def test_inbound_request_id_is_honored(client):
    resp = await client.get("/health", headers={"X-Request-ID": "proxy-abc-123"})
    assert resp.headers["x-request-id"] == "proxy-abc-123"


async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


async def test_error_boundary_hides_internals(client):
    """Unhandled exceptions must produce a clean 500 + error_id — the
    exception message (which may contain paths, SQL, keys) never reaches
    the client."""
    from backend.main import app

    @app.get("/_test_boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    try:
        resp = await client.get("/_test_boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"] == "Internal server error"
        assert body["error_id"] == resp.headers["x-request-id"]
        assert "secret internal detail" not in resp.text
    finally:
        app.router.routes[:] = [
            r for r in app.router.routes if getattr(r, "path", None) != "/_test_boom"
        ]


# ---------------------------------------------------------------------------
# Sliding-window rate limiter (pure unit — explicit clock)
# ---------------------------------------------------------------------------


def test_limiter_allows_up_to_budget():
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    assert all(limiter.check("ip", now=t)[0] for t in (0.0, 1.0, 2.0))


def test_limiter_blocks_over_budget_with_retry_after():
    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60)
    limiter.check("ip", now=0.0)
    limiter.check("ip", now=10.0)
    allowed, retry_after = limiter.check("ip", now=20.0)
    assert not allowed
    assert retry_after == 41  # oldest event (t=0) leaves the window at t=60

    # A denied attempt must not consume budget for later ones.
    allowed, _ = limiter.check("ip", now=61.0)
    assert allowed


def test_limiter_window_slides():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.check("ip", now=0.0)[0]
    assert not limiter.check("ip", now=59.0)[0]
    assert limiter.check("ip", now=61.0)[0]


def test_limiter_keys_are_independent_and_prunable():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.check("a", now=0.0)[0]
    assert limiter.check("b", now=0.0)[0]  # b unaffected by a's budget
    limiter.prune(now=120.0)
    assert limiter._events == {}


# ---------------------------------------------------------------------------
# Concurrency gate
# ---------------------------------------------------------------------------


def test_run_gate_caps_concurrency():
    gate = RunGate(capacity=2)
    gate.acquire()
    gate.acquire()
    with pytest.raises(CapacityError):
        gate.acquire()
    gate.release()
    gate.acquire()  # slot freed


# ---------------------------------------------------------------------------
# Endpoint enforcement (dependency + gate wired into the routes)
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_pipeline(monkeypatch):
    async def fake_pipeline(ticker, user_id, db, plan_limits=None):
        return {"type": "complete", "ticker": ticker}

    monkeypatch.setattr("backend.api.routes_research.run_research_pipeline", fake_pipeline)


async def test_research_endpoint_rate_limited(client, stub_pipeline, monkeypatch):
    monkeypatch.setattr(
        "backend.api.limits.research_limiter",
        SlidingWindowLimiter(max_requests=1, window_seconds=3600),
    )
    first = await client.post("/api/research", json={"ticker": "NVDA"})
    assert first.status_code == 200

    second = await client.post("/api/research", json={"ticker": "NVDA"})
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) > 0
    assert "Rate limit" in second.json()["detail"]


async def test_research_endpoint_rejects_when_at_capacity(client, stub_pipeline, monkeypatch):
    monkeypatch.setattr("backend.api.routes_research.run_gate", RunGate(capacity=0))
    resp = await client.post("/api/research", json={"ticker": "NVDA"})
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "60"


async def test_gate_slot_released_after_run(client, stub_pipeline, monkeypatch):
    gate = RunGate(capacity=1)
    monkeypatch.setattr("backend.api.routes_research.run_gate", gate)
    resp = await client.post("/api/research", json={"ticker": "NVDA"})
    assert resp.status_code == 200
    assert gate.active == 0


# ---------------------------------------------------------------------------
# Agent timeout
# ---------------------------------------------------------------------------


async def test_traced_run_times_out_hung_agent(monkeypatch):
    from backend.core.config import settings

    async def hung_run(agent, input_text, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr("backend.pipeline.tracing.Runner.run", hung_run)
    monkeypatch.setattr(settings, "agent_timeout_seconds", 0.05)

    fake_agent = types.SimpleNamespace(name="HungAgent", model="test-model")
    with pytest.raises(AgentTimeoutError, match="HungAgent"):
        await traced_run(fake_agent, "input", phase="research")


# ---------------------------------------------------------------------------
# Health probes
# ---------------------------------------------------------------------------


async def test_liveness_has_no_dependencies(client):
    resp = await client.get("/health")
    assert resp.json()["status"] == "ok"


async def test_readiness_reports_database_up(client):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "up"}
