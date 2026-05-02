from agents import Agent
from app.core.config import settings
from app.schemas.research import ResearchReport
from app.tools.persistence import save_artifact

synthesizer_agent = Agent(
    name="Report Synthesizer",
    model=settings.default_model,
    instructions="""
    You are the final stage synthesizer. You receive structured
    outputs from research, fundamentals, sentiment, and research agents.
    You produce a single research report.
    HARD RULES: \n
    1. Every numeric claim MUSTbetraceable to a tool result in context.\n
    2. bull_case and bear_case must be 3-5 items each.\n
    3. confidence reflects evidence strength, not your enthusiasm.\n
    4. recommendationmay be'no_view' if evidence is too thin.\n
    5. Always call save_artifact at the end.
    """,
    output_type=ResearchReport,
    tools=[save_artifact],
)
