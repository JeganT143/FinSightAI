import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from agents import Runner
from backend.agents.fundamentals import fundamentals_agent
from backend.agents.risk import risk_agent
from backend.agents.sentiment import sentiment_agent
from backend.agents.synthesizer import synthesizer_agent
from backend.agents.critic import critic_agent
from backend.schemas.critic import CriticOutput
from backend.db import crud
from backend.db.models import ResearchReport


async def run_research_pipeline_stream(
    ticker: str,
    db: AsyncSession
) -> AsyncGenerator[dict, None]:
    """
    Runs the full pipeline, yields SSE events, persists results to database.
    """

    # Create report row immediately
    report: ResearchReport = await crud.create_report(db, ticker)
    report_id = str(report.id)

    yield {"type": "start", "message": f"Starting research for {ticker}", "report_id": report_id}

    try:
        # Phase 1 — parallel research
        yield {"type": "progress", "message": "Running specialist agents in parallel..."}

        fundamentals_result, risk_result, sentiment_result = await asyncio.gather(
            Runner.run(fundamentals_agent, f"Analyze {ticker}"),
            Runner.run(risk_agent, f"Analyze {ticker}"),
            Runner.run(sentiment_agent, f"Analyze {ticker}")
        )

        fundamentals_output = fundamentals_result.final_output
        risk_output = risk_result.final_output
        sentiment_output = sentiment_result.final_output

        yield {"type": "progress", "message": "Specialist research complete"}
        yield {"type": "fundamentals", "data": fundamentals_output}
        yield {"type": "risk", "data": risk_output}
        yield {"type": "sentiment", "data": sentiment_output}

        combined = f"""
        FUNDAMENTALS: {fundamentals_output}
        RISK: {risk_output}
        SENTIMENT: {sentiment_output}
        """

        # Phase 2 — synthesize
        yield {"type": "progress", "message": "Synthesizing report..."}
        synthesis = await Runner.run(synthesizer_agent, combined)
        report_v1 = synthesis.final_output
        yield {"type": "progress", "message": "Report draft ready"}

        # Phase 3 — critic
        yield {"type": "progress", "message": "Running critic review..."}
        critic_result = await Runner.run(
            critic_agent,
            f"RESEARCH DATA:\n{combined}\n\nREPORT:\n{report_v1}"
        )
        critic_output: CriticOutput = critic_result.final_output

        yield {
            "type": "critic",
            "challenges_found": len(critic_output.challenges),
            "blocks_publication": critic_output.blocks_publication,
            "assessment": critic_output.overall_assessment
        }

        # Phase 4 — revise if needed
        report_v2 = None
        was_revised = False

        if critic_output.blocks_publication:
            yield {"type": "progress", "message": "Revising report based on critic feedback..."}
            revision = await Runner.run(
                synthesizer_agent,
                f"""
                RESEARCH DATA: {combined}
                PREVIOUS REPORT: {report_v1}
                CHALLENGES: {critic_output.challenges}
                Revise the report addressing all challenges.
                """
            )
            report_v2 = revision.final_output
            was_revised = True

        final_report = report_v2 if was_revised else report_v1

        # Persist to database
        await crud.complete_report(
            db=db,
            report=report,
            report_v1=report_v1,
            report_v2=report_v2,
            was_revised=was_revised,
            fundamentals_output=fundamentals_output,
            risk_output=risk_output,
            sentiment_output=sentiment_output,
            critic_challenges_found=len(critic_output.challenges),
            critic_assessment=critic_output.overall_assessment,
        )

        yield {
            "type": "complete",
            "ticker": ticker,
            "report_id": report_id,
            "report": final_report,
            "was_revised": was_revised
        }

    except Exception as e:
        await crud.fail_report(db, report, str(e))
        yield {"type": "error", "message": str(e)}
        raise


async def run_research_pipeline(
    ticker: str,
    db: AsyncSession
) -> tuple[str, bool, str]:
    """Non-streaming version. Returns (report, was_revised, report_id)."""
    report_text = ""
    was_revised = False
    report_id = ""

    async for event in run_research_pipeline_stream(ticker, db):
        if event["type"] == "complete":
            report_text = event["report"]
            was_revised = event["was_revised"]
            report_id = event["report_id"]

    return report_text, was_revised, report_id
