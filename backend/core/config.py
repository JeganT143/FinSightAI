import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    database_url: str
    app_name: str = "FinSightAI"
    app_version: str = "0.2.0"
    debug: bool = False

    # --- Model routing (ADR-4): cheap specialists, stronger synthesis/critique ---
    specialist_model: str = "gpt-4o-mini"
    synthesizer_model: str = "gpt-4o"
    critic_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- Pipeline guardrails (ADR-6) ---
    max_revisions: int = 2
    max_cost_usd: float = 0.50  # circuit breaker: abort revision loop past this spend
    agent_timeout_seconds: float = 180.0  # one hung LLM call must not hang the run forever

    # --- Operational guardrails (ADR-12) ---
    max_concurrent_runs: int = 2  # parallel pipeline runs; excess gets 503 + Retry-After
    rate_limit_runs: int = 10  # research runs per client IP per window
    rate_limit_window_seconds: int = 3600

    # --- Logging (ADR-12) ---
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"  # "json" in containers (see compose)

    # --- RAG over SEC filings (ADR-5) ---
    # SEC requires a User-Agent identifying the requester: https://www.sec.gov/os/accessing-edgar-data
    sec_user_agent: str = "FinSightAI/0.2 (research demo; contact: engjegant@gmail.com)"
    rag_top_k: int = 5
    chunk_size_tokens: int = 800
    chunk_overlap_tokens: int = 100

    # --- API ---
    cors_origins: list[str] = ["http://localhost:3000"]


# USD per 1M tokens: (input, output). Used to convert usage -> cost per agent run.
MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Convert token usage to USD. Unknown models cost 0 rather than crashing a run."""
    input_price, output_price = MODEL_PRICING_PER_1M.get(model, (0.0, 0.0))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


settings = Settings()
