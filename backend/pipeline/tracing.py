"""First-party agent-run tracing (ADR-8): wrap every Runner.run with wall-clock
timing and token/cost extraction so the pipeline can persist per-agent traces
and stream usage to the UI."""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agents import Agent, Runner
from pydantic import BaseModel

from backend.core.config import estimate_cost_usd


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class TracedRun:
    agent_name: str
    phase: str
    model: str
    output: Any  # the agent's typed output (a Pydantic model)
    input_tokens: int
    output_tokens: int
    requests: int
    cost_usd: float
    latency_ms: int
    started_at: datetime
    finished_at: datetime

    @property
    def output_dict(self) -> dict:
        if isinstance(self.output, BaseModel):
            return self.output.model_dump()
        return {"text": str(self.output)}

    @property
    def usage_event(self) -> dict:
        """The `usage` payload attached to agent_completed SSE events."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": self.latency_ms,
            "model": self.model,
        }


async def traced_run(agent: Agent, input_text: str, phase: str) -> TracedRun:
    """Run an agent and capture output + usage + latency in one record."""
    started = _utcnow()
    t0 = time.perf_counter()

    result = await Runner.run(agent, input_text)

    latency_ms = int((time.perf_counter() - t0) * 1000)
    usage = result.context_wrapper.usage
    model = str(agent.model)

    return TracedRun(
        agent_name=agent.name,
        phase=phase,
        model=model,
        output=result.final_output,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        requests=usage.requests,
        cost_usd=estimate_cost_usd(model, usage.input_tokens, usage.output_tokens),
        latency_ms=latency_ms,
        started_at=started,
        finished_at=_utcnow(),
    )
