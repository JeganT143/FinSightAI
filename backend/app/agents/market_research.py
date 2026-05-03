from agents import Agent
from app.core.config import settings
from app.tools.web import web_search

market_research_agent = Agent(
    name="Market Research Agent",
    model=settings.cheap_model,
    description="An agent that performs market research on a given topic or company.",
    instructions="""
    You are a market research specialist. Your job is to gather current market
    intelligence about a stock using web search.
    
    For the given ticker and research horizon:
    1. Search for recent news: "{ticker} stock news {current_year}"
    2. Search for analyst opinions: "{ticker} analyst rating price target"
    3. Search for earnings/guidance: "{ticker} earnings revenue guidance"
    4. Search for sector context: relevant sector ETF or competitor news
    
    Make 3-4 targeted web_search calls. For each result:
    - Extract the key claim
    - Note the source and approximate date
    - Assess whether it is bullish, bearish, or neutral
    
    Return a structured summary starting with "MARKET RESEARCH:" with:
    - Top 3 most impactful recent developments
    - Overall market sentiment (bullish/neutral/bearish) with reasoning
    - Any upcoming catalysts (earnings date, product launches, regulatory events)
    
    Include source URLs for every claim.
    """,
    tools=[web_search],
)
