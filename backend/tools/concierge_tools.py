"""LLM-facing Concierge tools (SAAS §8.3): thin @function_tool wrappers whose
docstrings are the model's interface. Logic lives in backend/concierge/actions.py
(directly unit-tested); tenancy comes from a ContextVar there, never from the
model."""

from agents import function_tool

from backend.concierge import actions
from backend.concierge.actions import current_user_id_var  # re-export for callers

__all__ = [
    "current_user_id_var",
    "get_account_status",
    "get_report",
    "search_past_reports",
    "trigger_research",
]


@function_tool
async def trigger_research(ticker: str) -> dict:
    """Start a full research run for a stock ticker. Returns the report_id the
    user can watch. Use ONLY when the user asks to research/analyze a ticker
    and no recent report exists (check search_past_reports first).

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    return await actions.trigger_research(ticker)


@function_tool
async def get_report(report_id: str) -> dict:
    """Fetch one of the user's research reports by id (full structured report).

    Args:
        report_id: The report's UUID
    """
    return await actions.get_report(report_id)


@function_tool
async def search_past_reports(query: str) -> dict:
    """List the user's recent reports, optionally narrowed by a ticker symbol
    found in the query. Use before trigger_research to avoid duplicate runs.

    Args:
        query: Free text; a ticker symbol in it (e.g. 'NVDA') narrows results
    """
    return await actions.search_past_reports(query)


@function_tool
async def get_account_status() -> dict:
    """The user's plan and current-period usage (runs used / limit)."""
    return await actions.get_account_status()
