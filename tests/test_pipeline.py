"""Orchestrator logic tests (ADR-1/ADR-6): scripted agent results, zero LLM calls.

traced_run and filing ingestion are patched out; the real crud layer runs
against SQLite, so persistence is exercised too.
"""

import pytest
from sqlalchemy import select

from backend.db.models import AgentRun, ResearchReport
from backend.pipeline.research import run_research_pipeline_stream
from backend.rag.ingest import IngestStatus
from tests.factories import make_critic, make_draft, make_specialist, make_traced_run


class ScriptedAgents:
    """Returns canned TracedRuns; critic verdicts pop from a script list."""

    def __init__(self, critic_script: list[bool]):
        self.critic_script = list(critic_script)
        self.synth_calls = 0

    async def __call__(self, agent, input_text: str, phase: str):
        name = agent.name
        if name == "CriticAgent":
            return make_traced_run(name, phase, make_critic(blocks=self.critic_script.pop(0)))
        if name == "SynthesizerAgent":
            self.synth_calls += 1
            return make_traced_run(name, phase, make_draft())
        return make_traced_run(name, phase, make_specialist(name))


@pytest.fixture
def no_rag(monkeypatch):
    async def fake_ingest(db, ticker):
        return IngestStatus(status="unavailable", detail="test mode")

    monkeypatch.setattr("backend.pipeline.research.ensure_filing_ingested", fake_ingest)


async def collect_events(ticker, db):
    return [event async for event in run_research_pipeline_stream(ticker, db)]


async def test_clean_run_no_revision(db_session, no_rag, monkeypatch):
    monkeypatch.setattr(
        "backend.pipeline.research.traced_run", ScriptedAgents(critic_script=[False])
    )
    events = await collect_events("NVDA", db_session)

    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types.count("agent_started") == 6  # 4 specialists + synthesizer + critic
    assert types.count("agent_completed") == 5  # critic reports via critic_verdict
    assert types.count("critic_verdict") == 1
    assert types[-1] == "complete"

    complete = events[-1]
    assert complete["revision_count"] == 0
    assert complete["report"]["verdict"] == "BUY"
    # overall score recomputed in code from specialist scores (all 7.0)
    assert complete["report"]["overall_score"] == 7.0
    assert complete["usage_summary"]["cost_usd"] > 0

    report = (await db_session.execute(select(ResearchReport))).scalar_one()
    assert report.status == "complete"
    runs = (await db_session.execute(select(AgentRun))).scalars().all()
    assert len(runs) == 6


async def test_blocked_report_gets_revised_once(db_session, no_rag, monkeypatch):
    script = ScriptedAgents(critic_script=[True, False])  # block, then approve
    monkeypatch.setattr("backend.pipeline.research.traced_run", script)
    events = await collect_events("NVDA", db_session)

    complete = events[-1]
    assert complete["revision_count"] == 1
    assert script.synth_calls == 2  # initial + one revision
    verdicts = [e for e in events if e["type"] == "critic_verdict"]
    assert len(verdicts) == 2
    assert verdicts[0]["blocks_publication"] is True
    assert verdicts[1]["blocks_publication"] is False


async def test_revision_loop_is_bounded(db_session, no_rag, monkeypatch):
    """Critic that never approves must not loop forever (ADR-6)."""
    script = ScriptedAgents(critic_script=[True] * 10)
    monkeypatch.setattr("backend.pipeline.research.traced_run", script)
    events = await collect_events("NVDA", db_session)

    complete = events[-1]
    from backend.core.config import settings

    assert complete["revision_count"] == settings.max_revisions
    verdicts = [e for e in events if e["type"] == "critic_verdict"]
    assert len(verdicts) == settings.max_revisions + 1
    # published despite unresolved challenges — flagged, not hidden
    assert complete["critic"]["blocks_publication"] is True


async def test_specialist_failure_marks_report_failed(db_session, no_rag, monkeypatch):
    async def exploding_run(agent, input_text, phase):
        raise RuntimeError("tool exploded")

    monkeypatch.setattr("backend.pipeline.research.traced_run", exploding_run)

    events = []
    with pytest.raises(RuntimeError):
        async for event in run_research_pipeline_stream("NVDA", db_session):
            events.append(event)

    assert events[-1]["type"] == "error"
    report = (await db_session.execute(select(ResearchReport))).scalar_one()
    assert report.status == "failed"
    assert "tool exploded" in report.error
