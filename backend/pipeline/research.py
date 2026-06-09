import asyncio
from agents import Runner
from backend.agents.fundamentals import fundamentals_agent
from backend.agents.risk import risk_agent
from backend.agents.sentiment import sentiment_agent
from backend.agents.synthesizer import synthesizer_agent
from backend.agents.critic import critic_agent
from backend.schemas.critic import CriticOutput


async def run_research_pipeline(ticker: str) -> tuple[str, bool]:
    """
    Runs the full multi-agent research pipeline.
    Returns: (final_report, was_revised)
    """

    # Phase 1 — parallel specialist research
    fundamentals_result, risk_result, sentiment_result = await asyncio.gather(
        Runner.run(fundamentals_agent, f"Analyze {ticker}"),
        Runner.run(risk_agent, f"Analyze {ticker}"),
        Runner.run(sentiment_agent, f"Analyze {ticker}"),
    )

    combined = f"""
    FUNDAMENTALS: {fundamentals_result.final_output}
    RISK: {risk_result.final_output}
    SENTIMENT: {sentiment_result.final_output}
    """

    # Phase 2 — synthesize
    synthesis = await Runner.run(synthesizer_agent, combined)
    report_v1 = synthesis.final_output

    # Phase 3 — critic review
    critic_result = await Runner.run(
        critic_agent, f"RESEARCH DATA:\n{combined}\n\nREPORT:\n{report_v1}"
    )
    critic_output: CriticOutput = critic_result.final_output

    # Phase 4 — revise if critic blocks publication
    if critic_output.blocks_publication:
        revision = await Runner.run(
            synthesizer_agent,
            f"""
            RESEARCH DATA: {combined}
            PREVIOUS REPORT: {report_v1}
            CHALLENGES: {critic_output.challenges}
            Revise the report addressing all challenges.
            """,
        )
        return revision.final_output, True

    return report_v1, False
