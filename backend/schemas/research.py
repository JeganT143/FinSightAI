from datetime import datetime

from pydantic import BaseModel, field_validator


class ResearchRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        ticker = v.upper().strip()
        if not ticker.isalpha():
            raise ValueError("Ticker must only contain letters")
        if not 1 <= len(ticker) <= 5:
            raise ValueError("Ticker must be 1-5 characters long")
        return ticker


class UsageSummary(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int | None


class ReportSummary(BaseModel):
    """List-view row for report history."""

    id: str
    ticker: str
    status: str
    verdict: str | None
    overall_score: float | None
    revision_count: int
    cost_usd: float
    latency_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]
    total: int
    limit: int
    offset: int


class AgentRunDetail(BaseModel):
    agent_name: str
    phase: str
    status: str
    model: str
    output: dict | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    started_at: datetime
    finished_at: datetime | None


class ReportDetailResponse(BaseModel):
    id: str
    ticker: str
    status: str
    verdict: str | None
    overall_score: float | None
    report: dict | None
    critic: dict | None
    revision_count: int
    error: str | None
    usage: UsageSummary
    agent_runs: list[AgentRunDetail]
    created_at: datetime
    completed_at: datetime | None
