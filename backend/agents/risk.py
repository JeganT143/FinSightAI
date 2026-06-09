from agents import Agent
from backend.tools.risk import get_risk_metrics

risk_agent = Agent(
    name="RiskAgent",
    model="gpt-4o-mini",
    instructions="""
    You are a risk assessment specialist.
    ALWAYS call get_risk_metrics before writing anything.
    
    Output exactly 3 bullet points with specific numbers.
    End with: RISK_SCORE: [1-10] (10 = highest risk)
    """,
    tools=[get_risk_metrics],
)
