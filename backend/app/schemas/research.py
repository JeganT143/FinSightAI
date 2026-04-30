from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=8)
    question: str = Field(..., min_length=4, max_length=4000)
    horizon: Literal["1w", "1m", "3m", "6m", "1y"] = "3m"


class Citation(BaseModel):
    title: str
    url: str
    accessed_at: datetime


class ResearchReport(BaseModel):
    """Structured output of the synthesizer agent"""

    ticker: str
    thesis: str
    bull_case: str
    bear_case: str
    key_metrics: dict[str, float]
    risks: list[str]
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    recomendation: Literal["buy", "hold", "sell", "no_view"]
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation]


class ResearchResponse(BaseModel):
    session_id: UUID
    report: ResearchReport
