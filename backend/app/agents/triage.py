from agents import Agent
from app.agents.fundamentals import fundamentals_agent
from app.agents.market_research import market_research_agent
from app.agents.risk import risk_agent
from app.agents.sentiment import sentiment_agent
from app.agents.synthesizer import synthesizer_agent
from app.core.config import settings

triage_agent = Agent(
    name="Triage Agent",
    model=settings.cheap_model,
    instructions="""
    You are the triage agent. Your job is to take an incoming research request and determine which agents should be called to fulfill the request. 
    You have access to the following agents: market_research_agent, fundamentals_agent, sentiment_agent, risk_agent, synthesizer_agent.
    Your output should be a list of agents to call in order, along with any necessary input for each agent.
    """,
    handoffs=[
        market_research_agent,
        fundamentals_agent,
        sentiment_agent,
        risk_agent,
        synthesizer_agent,
    ],
)
