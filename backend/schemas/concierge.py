"""Typed contract for a Concierge turn (SAAS §8.5) — same discipline as
schemas/agents.py: nothing downstream parses free text."""

from pydantic import BaseModel, Field


class ConciergeTurn(BaseModel):
    content: str = Field(description="The assistant's reply, markdown allowed")
    tool_calls_made: list[str] = Field(
        description="Names of tools called this turn, in order; empty list if none"
    )
    linked_report_id: str | None = Field(
        description="Report id this reply centers on (from trigger_research/get_report), else null"
    )
