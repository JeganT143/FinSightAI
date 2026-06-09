from agents import Agent
from backend.tools.fundamentals import get_fundamentals

fundamentals_agent = Agent(
    name="FundamentalsAgent",
    model="gpt-4o-mini",
    instructions="""
    You are a fundamental analysis specialist.
    ALWAYS call get_fundamentals before writing anything.
    
    Output exactly 3 bullet points with specific numbers.
    End with: FUNDAMENTALS_SCORE: [1-10]
    """,
    tools=[get_fundamentals],
)
