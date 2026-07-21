"""The research orchestrator (ADR-1): a deterministic graph in plain Python.

Phases:
  0. grounding   — ensure the latest SEC filing is ingested (best-effort)
  1. research    — 4 specialist agents in parallel, streamed as each finishes
  2. synthesis   — typed specialist outputs -> ReportDraft
  3. critique    — adversarial review; bounded revision loop (ADR-6)
  4. persistence — report + per-agent traces + cost totals

Agents never choose the topology; only the critic's typed verdict gates the
one loop, and that loop is bounded by max_revisions and max_cost_usd.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.critic import critic_agent
from backend.agents.fundamentals import fundamentals_agent
from backend.agents.risk import risk_agent
from backend.agents.sentiment import sentiment_agent
from backend.agents.synthesizer import synthesizer_agent
from backend.agents.technicals import technicals_agent
from backend.core.config import settings
from backend.db import crud
from backend.db.models import ResearchReport
from backend.pipeline.tracing import TracedRun, traced_run
from backend.rag.ingest import ensure_filing_ingested
from backend.schemas.agents import (
    CriticOutput,
    ReportDraft,
    SpecialistOutput,
    compute_overall_score,
)

logger = logging.getLogger(__name__)

SPECIALISTS = {
    "fundamentals": fundamentals_agent,
    "technicals": technicals_agent,
    "risk": risk_agent,
    "sentiment": sentiment_agent,
}

AGENT_TO_PILLAR = {agent.name: pillar for pillar, agent in SPECIALISTS.items()}


def _specialists_payload(outputs: dict[str, SpecialistOutput], overall_score: float) -> str:
    return json.dumps(
        {
            "specialist_outputs": {k: v.model_dump() for k, v in outputs.items()},
            "computed_overall_score": overall_score,
        },
        indent=2,
    )


async def run_research_pipeline_stream(ticker: str, db: AsyncSession) -> AsyncGenerator[dict]:
    """Runs the full pipeline, yielding SSE events and persisting as it goes."""
    t0 = time.perf_counter()
    report: ResearchReport = await crud.create_report(db, ticker)
    # Commit immediately: the running row shows up in the Ledger, and a crash
    # later still leaves a traceable failed report.
    await db.commit()
    report_id = str(report.id)
    logger.info("run started: report=%s ticker=%s", report_id, ticker)

    total_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0

    async def record(run: TracedRun) -> None:
        nonlocal total_cost, total_input_tokens, total_output_tokens
        total_cost += run.cost_usd
        total_input_tokens += run.input_tokens
        total_output_tokens += run.output_tokens
        await crud.add_agent_run(db, report.id, run)

    yield {"type": "start", "report_id": report_id, "ticker": ticker}

    try:
        # ---- Phase 0: grounding --------------------------------------------
        yield {"type": "phase", "phase": "grounding", "message": "Ingesting latest SEC filing..."}
        ingest = await ensure_filing_ingested(db, ticker)
        # Commit NOW: the search_filings tool reads through its own session,
        # which cannot see this session's uncommitted chunks.
        await db.commit()
        total_cost += ingest.embedding_cost_usd
        yield {
            "type": "grounding",
            "status": ingest.status,
            "detail": ingest.detail,
            "form_type": ingest.form_type,
            "filing_date": ingest.filing_date,
            "chunk_count": ingest.chunk_count,
        }

        # ---- Phase 1: parallel specialist research -------------------------
        yield {
            "type": "phase",
            "phase": "research",
            "message": "Specialist agents researching in parallel...",
        }

        async def run_specialist(pillar: str) -> TracedRun:
            return await traced_run(SPECIALISTS[pillar], f"Analyze {ticker}", phase="research")

        tasks = [asyncio.create_task(run_specialist(p)) for p in SPECIALISTS]
        for pillar in SPECIALISTS:
            yield {"type": "agent_started", "agent": pillar, "phase": "research"}

        outputs: dict[str, SpecialistOutput] = {}
        try:
            for future in asyncio.as_completed(tasks):
                run = await future
                pillar = AGENT_TO_PILLAR[run.agent_name]
                outputs[pillar] = run.output
                await record(run)
                yield {
                    "type": "agent_completed",
                    "agent": pillar,
                    "phase": "research",
                    "data": run.output_dict,
                    "usage": run.usage_event,
                }
        except BaseException:
            # One specialist failed: cancel the siblings so they stop consuming
            # tokens, and observe their results so no exception goes unretrieved.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        overall_score = compute_overall_score(
            fundamentals=outputs["fundamentals"],
            risk=outputs["risk"],
            sentiment=outputs["sentiment"],
            technicals=outputs["technicals"],
        )
        payload = _specialists_payload(outputs, overall_score)

        # ---- Phase 2: synthesis ---------------------------------------------
        yield {"type": "phase", "phase": "synthesis", "message": "Synthesizing report..."}
        yield {"type": "agent_started", "agent": "synthesizer", "phase": "synthesis"}

        synth_run = await traced_run(
            synthesizer_agent, f"TICKER: {ticker}\n\n{payload}", phase="synthesis"
        )
        draft: ReportDraft = synth_run.output
        draft.overall_score = overall_score  # deterministic arithmetic wins (ADR-3)
        await record(synth_run)
        yield {
            "type": "agent_completed",
            "agent": "synthesizer",
            "phase": "synthesis",
            "data": draft.model_dump(),
            "usage": synth_run.usage_event,
        }

        # ---- Phase 3: adversarial critique + bounded revision (ADR-6) -------
        revision_count = 0
        critic_output: CriticOutput | None = None

        while True:
            yield {
                "type": "phase",
                "phase": "critique",
                "message": "Adversarial review in progress...",
            }
            yield {"type": "agent_started", "agent": "critic", "phase": "critique"}

            critic_run = await traced_run(
                critic_agent,
                f"SPECIALIST DATA (ground truth):\n{payload}\n\nDRAFT REPORT:\n{draft.model_dump_json(indent=2)}",
                phase="critique",
            )
            critic_output = critic_run.output
            await record(critic_run)
            yield {
                "type": "critic_verdict",
                "revision": revision_count,
                "challenges": [c.model_dump() for c in critic_output.challenges],
                "blocks_publication": critic_output.blocks_publication,
                "assessment": critic_output.overall_assessment,
                "usage": critic_run.usage_event,
            }

            if not critic_output.blocks_publication:
                break
            if revision_count >= settings.max_revisions:
                yield {
                    "type": "phase",
                    "phase": "revision",
                    "message": f"Max revisions ({settings.max_revisions}) reached — publishing with unresolved challenges flagged.",
                }
                break
            if total_cost >= settings.max_cost_usd:
                yield {
                    "type": "phase",
                    "phase": "revision",
                    "message": f"Cost circuit breaker (${settings.max_cost_usd:.2f}) tripped — publishing with challenges flagged.",
                }
                break

            revision_count += 1
            yield {
                "type": "phase",
                "phase": "revision",
                "message": f"Revising report (round {revision_count}) to address critic challenges...",
            }
            yield {"type": "agent_started", "agent": "synthesizer", "phase": "revision"}

            revision_run = await traced_run(
                synthesizer_agent,
                (
                    f"TICKER: {ticker}\n\n{payload}\n\n"
                    f"PREVIOUS DRAFT:\n{draft.model_dump_json(indent=2)}\n\n"
                    f"CRITIC CHALLENGES (address every one):\n{critic_output.model_dump_json(indent=2)}"
                ),
                phase="revision",
            )
            draft = revision_run.output
            draft.overall_score = overall_score
            await record(revision_run)
            yield {
                "type": "agent_completed",
                "agent": "synthesizer",
                "phase": "revision",
                "data": draft.model_dump(),
                "usage": revision_run.usage_event,
            }

        # ---- Phase 4: persistence -------------------------------------------
        latency_ms = int((time.perf_counter() - t0) * 1000)
        await crud.complete_report(
            db=db,
            report=report,
            draft=draft,
            critic=critic_output,
            revision_count=revision_count,
            prompt_tokens=total_input_tokens,
            completion_tokens=total_output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
        )

        logger.info(
            "run complete: report=%s ticker=%s verdict=%s score=%.1f revisions=%d "
            "tokens=%d/%d cost=$%.4f latency=%dms",
            report_id,
            ticker,
            draft.verdict,
            draft.overall_score,
            revision_count,
            total_input_tokens,
            total_output_tokens,
            total_cost,
            latency_ms,
        )

        yield {
            "type": "complete",
            "report_id": report_id,
            "ticker": ticker,
            "report": draft.model_dump(),
            "critic": critic_output.model_dump(),
            "revision_count": revision_count,
            "usage_summary": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost_usd": round(total_cost, 6),
                "latency_ms": latency_ms,
            },
        }

    except Exception as e:
        # Full detail goes to the log and the report row; the SSE event (readable
        # by any anonymous client in Phase 1) gets the exception class only.
        logger.exception("run failed: report=%s ticker=%s", report_id, ticker)
        await crud.fail_report(db, report, str(e))
        yield {
            "type": "error",
            "message": f"Research run failed ({type(e).__name__}). "
            "Full detail is stored on the report.",
            "report_id": report_id,
        }
        raise


async def run_research_pipeline(ticker: str, db: AsyncSession) -> dict:
    """Non-streaming variant: drains the stream, returns the `complete` payload."""
    final: dict = {}
    async for event in run_research_pipeline_stream(ticker, db):
        if event["type"] == "complete":
            final = event
    return final
