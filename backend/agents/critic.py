from agents import Agent
from backend.schemas.critic import CriticOutput

critic_agent = Agent(
    name="CriticAgent",
    model="gpt-4o-mini",
    instructions="""
    You are an adversarial reviewer for investment reports.
    
    Check every claim in the report:
    - Is this number actually in the specialist data?
    - Is this conclusion logically supported by the data?
    - Did the synthesizer make assumptions not in the data?
    
    Be strict. Output structured challenges only.
    """,
    output_type=CriticOutput
)
