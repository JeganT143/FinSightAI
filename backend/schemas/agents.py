"""Typed contracts between agents (ADR-3).

Every agent produces one of these models via the Agents SDK `output_type`.
Nothing downstream parses free text: the synthesizer consumes specialist models
as JSON, the critic verifies the draft against them, the DB stores them as
JSONB, and the frontend renders fields directly.

NOTE: fields deliberately have NO defaults — OpenAI strict structured outputs
require every field to be present, and required-everywhere keeps the JSON
schema strict-mode compatible.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")

Pillar = Literal["fundamentals", "technicals", "risk", "sentiment"]

Verdict = Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]


class Citation(BaseModel):
    """A pointer into a SEC filing chunk returned by the search_filings tool."""

    source: str = Field(description="e.g. '10-K 2026-02-14 Item 1A — Risk Factors'")
    quote: str = Field(description="Short verbatim passage (<= 40 words) backing the claim")

    @field_validator("source", "quote")
    @classmethod
    def strip_control_chars(cls, v: str) -> str:
        """Models occasionally garble em-dashes into control bytes; scrub them."""
        return _CONTROL_CHARS.sub(" ", v).strip()


class SpecialistOutput(BaseModel):
    """Common contract for the four specialist agents."""

    score: float = Field(ge=0, le=10, description="0 = worst, 10 = best for this pillar")
    confidence: Literal["low", "medium", "high"] = Field(
        description="How complete/reliable the underlying data was"
    )
    summary: str = Field(description="1-2 sentence headline finding")
    bullets: list[str] = Field(
        description="3-5 evidence bullets, each containing specific numbers from tool output"
    )
    data_warnings: list[str] = Field(
        description="Fields that were missing/null in tool output; empty list if none"
    )


class FundamentalsOutput(SpecialistOutput):
    citations: list[Citation] = Field(
        description="Filing passages consulted via search_filings; empty list if unavailable"
    )


class RiskOutput(SpecialistOutput):
    """Risk score convention: 10 = LOWEST risk (safest), so all pillar scores point the same way."""

    citations: list[Citation] = Field(
        description="Filing passages consulted via search_filings; empty list if unavailable"
    )


class TechnicalsOutput(SpecialistOutput):
    pass


class SentimentOutput(SpecialistOutput):
    pass


class PillarSummary(BaseModel):
    pillar: Pillar
    score: float = Field(ge=0, le=10)
    summary: str


class ReportDraft(BaseModel):
    """The synthesizer's product — the report itself, as data.

    `overall_score` is COMPUTED IN CODE from specialist scores (weighted; see
    pipeline.scoring) and overwritten after generation: we don't ask an LLM to
    do arithmetic we can do deterministically.
    """

    ticker: str
    verdict: Verdict
    overall_score: float = Field(ge=0, le=10)
    pillars: list[PillarSummary]
    thesis: str = Field(description="2-4 sentence investment thesis grounded in specialist data")
    key_risks: list[str] = Field(description="2-4 most material risks, most severe first")
    catalysts: list[str] = Field(description="1-3 things that could move the stock; empty if none")
    citations: list[Citation] = Field(description="Filing citations carried from specialists")
    narrative_markdown: str = Field(
        description="Full readable report in markdown. Every number must come from specialist data."
    )


class Challenge(BaseModel):
    claim: str = Field(description="The exact claim in the report being challenged")
    reason: str = Field(description="Why it's unsupported, contradicted, or overstated")
    severity: Literal["low", "medium", "high"]
    pillar: Pillar | None = Field(description="Which pillar the claim belongs to, if identifiable")


class CriticOutput(BaseModel):
    challenges: list[Challenge]
    blocks_publication: bool = Field(
        description="True only if any high-severity challenge means the report misleads"
    )
    overall_assessment: str = Field(description="1-3 sentence review summary")


# Weights for the deterministic overall score (risk is already 'higher = safer').
PILLAR_WEIGHTS: dict[str, float] = {
    "fundamentals": 0.35,
    "risk": 0.30,
    "sentiment": 0.20,
    "technicals": 0.15,
}


def compute_overall_score(
    fundamentals: SpecialistOutput,
    risk: SpecialistOutput,
    sentiment: SpecialistOutput,
    technicals: SpecialistOutput,
) -> float:
    """Weighted pillar score, rounded to one decimal. Done in code, not by the LLM (ADR-3)."""
    total = (
        fundamentals.score * PILLAR_WEIGHTS["fundamentals"]
        + risk.score * PILLAR_WEIGHTS["risk"]
        + sentiment.score * PILLAR_WEIGHTS["sentiment"]
        + technicals.score * PILLAR_WEIGHTS["technicals"]
    )
    return round(total, 1)


def verdict_band(overall_score: float) -> list[str]:
    """Verdicts consistent with a given overall score.

    Bands overlap on purpose at boundaries: the synthesizer may exercise judgment
    within a band, and the eval harness asserts membership, not equality.
    """
    if overall_score >= 8.0:
        return ["STRONG_BUY", "BUY"]
    if overall_score >= 6.5:
        return ["BUY", "HOLD"]
    if overall_score >= 4.5:
        return ["HOLD", "SELL", "BUY"]
    if overall_score >= 3.0:
        return ["SELL", "HOLD", "STRONG_SELL"]
    return ["STRONG_SELL", "SELL"]
