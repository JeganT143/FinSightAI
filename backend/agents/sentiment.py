from agents import Agent
from backend.tools.sentiment import get_market_sentiment

sentiment_agent = Agent(
    name="SentimentAgent",
    model="gpt-4o-mini",
    instructions="""
    You are a market sentiment specialist.
    ALWAYS call get_market_sentiment before writing anything.
    
    Output exactly 3 bullet points with specific numbers.
    End with: SENTIMENT_SCORE: [1-10]
    """,
    tools=[get_market_sentiment]
)