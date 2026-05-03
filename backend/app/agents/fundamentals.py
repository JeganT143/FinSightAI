from agents import Agent
from app.core.config import settings
from app.tools.market import get_fundamentals

fundamentals_agent = Agent(
    name="Fundamentals Agent",
    description="An agent that retrieves fundamental data for a given stock ticker.",
    model=settings.cheap_model,
    instructions="""
    You are a fundamental analysis specialist.
    Given a ticker symbol:
    1. call get_fundamentals(ticker) to retrieve the fundamental data for the stock.
    2. Interpret each metric in context:
        - PE ratio: compare to industry average (tech ~25, utilities ~18, banks ~12)
        - Price-to-book: <1.0 may indicate undervaluation
        - Revenue TTM: note trajectory if mentioned in context
        - EPS TTM: positive vs negative, trend matters
        - Market cap: categorize as nano/micro/small/mid/large cap
    3. Return a structured paragraph starting with "FUNDAMENTALS:" summarizing
       your interpretation with the raw numbers inline.
    4. Flag any red flags (negative EPS, extreme P/E, etc.)
    Be factual. Every claim must reference a number from get_fundamentals output
    """,
    tools=[get_fundamentals],
)
