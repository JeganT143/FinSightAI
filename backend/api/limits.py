"""Operational guardrails for the expensive endpoints (ADR-12).

A research run costs real money (~$0.02-0.05 of LLM spend) and real time
(~35s), and Phase 1 has no authentication — so the API itself must bound how
fast an anonymous caller can burn the operator's budget:

- ``SlidingWindowLimiter`` — per-client-IP request budget over a rolling
  window. In-process on purpose: one uvicorn process serves Phase 1, and a
  Redis-backed limiter is already specified for Phase 2
  (SAAS_ARCHITECTURE.md §6) when multiple workers exist.
- ``RunGate`` — caps *concurrent* pipeline runs regardless of caller, because
  N parallel runs multiply token spend and DB load. Excess requests get an
  immediate 503 + Retry-After instead of silently queueing (fail fast beats
  a mystery 3-minute hang).

Both live behind FastAPI dependencies / plain calls so tests exercise them
with their own instances instead of monkeypatching globals.
"""

import time
from collections import deque

from fastapi import HTTPException, Request

from backend.core.config import settings


class SlidingWindowLimiter:
    """Sliding-window-log rate limiter keyed by caller identity (client IP).

    Exact (no fixed-window boundary bursts) and tiny: one deque of timestamps
    per active caller, pruned on every check.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Record one attempt for `key`. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        window = self._events.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= self.max_requests:
            retry_after = int(window[0] + self.window_seconds - now) + 1
            return False, retry_after

        window.append(now)
        return True, 0

    def prune(self, now: float | None = None) -> None:
        """Drop callers with no events left in the window (memory hygiene)."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds
        for key in [k for k, w in self._events.items() if not w or w[-1] <= cutoff]:
            del self._events[key]


class CapacityError(Exception):
    """Raised by RunGate when all run slots are busy."""


class RunGate:
    """Non-queueing cap on concurrent pipeline runs.

    Single-event-loop counter — no lock needed; acquire/release never awaits.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.active = 0

    def acquire(self) -> None:
        if self.active >= self.capacity:
            raise CapacityError(
                f"All {self.capacity} research slots are busy; retry shortly."
            )
        self.active += 1

    def release(self) -> None:
        self.active = max(0, self.active - 1)


# Process-wide instances used by the routes (tests build their own).
research_limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_runs,
    window_seconds=settings.rate_limit_window_seconds,
)
run_gate = RunGate(capacity=settings.max_concurrent_runs)


def client_key(request: Request) -> str:
    """Rate-limit key: the direct peer address.

    Deliberately NOT trusting X-Forwarded-For — it's caller-controlled unless
    a trusted proxy strips it, and Phase 1 runs without one. Behind a real
    load balancer, switch to the proxy-verified header (SAAS_ARCHITECTURE.md).
    """
    return request.client.host if request.client else "unknown"


async def enforce_research_rate_limit(request: Request) -> None:
    """FastAPI dependency guarding the two research-run endpoints."""
    allowed, retry_after = research_limiter.check(client_key(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: {research_limiter.max_requests} research runs "
                f"per {int(research_limiter.window_seconds)}s per client."
            ),
            headers={"Retry-After": str(retry_after)},
        )
