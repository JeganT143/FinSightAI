"""Builders for typed test objects — no LLM anywhere near these."""

from datetime import UTC, datetime

from backend.pipeline.tracing import TracedRun
from backend.schemas.agents import (
    Challenge,
    CriticOutput,
    FundamentalsOutput,
    PillarSummary,
    ReportDraft,
    RiskOutput,
    SentimentOutput,
    SpecialistOutput,
    TechnicalsOutput,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


PILLAR_OUTPUT_TYPES = {
    "FundamentalsAgent": (FundamentalsOutput, {"citations": []}),
    "RiskAgent": (RiskOutput, {"citations": []}),
    "TechnicalsAgent": (TechnicalsOutput, {}),
    "SentimentAgent": (SentimentOutput, {}),
}


def make_specialist(agent_name: str, score: float = 7.0) -> SpecialistOutput:
    model, extra = PILLAR_OUTPUT_TYPES[agent_name]
    return model(
        score=score,
        confidence="high",
        summary=f"{agent_name} summary",
        bullets=["metric A is 42.5", "metric B is 17.3%", "metric C is 3.1x"],
        data_warnings=[],
        **extra,
    )


def make_draft(ticker: str = "NVDA", verdict: str = "BUY", score: float = 7.0) -> ReportDraft:
    return ReportDraft(
        ticker=ticker,
        verdict=verdict,
        overall_score=score,
        pillars=[
            PillarSummary(pillar=p, score=7.0, summary="s")
            for p in ("fundamentals", "technicals", "risk", "sentiment")
        ],
        thesis="Solid across pillars.",
        key_risks=["metric B is 17.3%"],
        catalysts=[],
        citations=[],
        narrative_markdown="## Investment Report: NVDA\nmetric A is 42.5",
    )


def make_critic(blocks: bool = False) -> CriticOutput:
    challenges = (
        [
            Challenge(
                claim="metric A is 42.5",
                reason="not supported",
                severity="high",
                pillar="fundamentals",
            )
        ]
        if blocks
        else []
    )
    return CriticOutput(
        challenges=challenges,
        blocks_publication=blocks,
        overall_assessment="blocked" if blocks else "clean",
    )


def make_traced_run(agent_name: str, phase: str, output) -> TracedRun:
    now = _utcnow()
    return TracedRun(
        agent_name=agent_name,
        phase=phase,
        model="test-model",
        output=output,
        input_tokens=100,
        output_tokens=50,
        requests=1,
        cost_usd=0.001,
        latency_ms=5,
        started_at=now,
        finished_at=now,
    )
