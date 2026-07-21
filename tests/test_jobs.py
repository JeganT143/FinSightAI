"""Queued execution tests (SAAS §7) — no Redis: the pub/sub surface is faked.

The live exit criterion (kill the worker mid-run, job re-picked-up) is a
compose-level manual check; these pin the seams: enqueue contract, publish
protocol (events + stream_end sentinel), and the relay's termination.
"""

import json
import uuid

import pytest

from backend.core.config import settings
from backend.db.models import User
from backend.jobs import research_job
from backend.jobs.research_job import STREAM_END, job_channel, run_research_job


class FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, json.loads(payload)))


@pytest.fixture
def queued_mode(monkeypatch):
    monkeypatch.setattr(settings, "queue_enabled", True)


async def test_run_research_job_publishes_events_and_sentinel(
    session_factory, db_session, monkeypatch
):
    user = User(email="queued@example.com", plan="pro")
    db_session.add(user)
    await db_session.commit()
    report_id = str(uuid.uuid4())

    async def canned_pipeline(ticker, user_id, db, plan_limits=None, existing_report_id=None):
        assert existing_report_id == uuid.UUID(report_id)  # adopts the API's row
        yield {"type": "start", "report_id": report_id, "ticker": ticker}
        yield {"type": "complete", "report_id": report_id, "ticker": ticker}

    monkeypatch.setattr(research_job, "run_research_pipeline_stream", canned_pipeline)
    monkeypatch.setattr(research_job, "AsyncSessionLocal", session_factory)

    redis = FakeRedis()
    await run_research_job({"redis": redis}, "NVDA", str(user.id), report_id)

    channels = {c for c, _ in redis.published}
    assert channels == {job_channel(report_id)}
    types = [e["type"] for _, e in redis.published]
    assert types == ["start", "complete", "stream_end"]


async def test_job_failure_still_sends_stream_end(session_factory, db_session, monkeypatch):
    user = User(email="queued2@example.com", plan="free")
    db_session.add(user)
    await db_session.commit()

    async def exploding_pipeline(*args, **kwargs):
        yield {"type": "start"}
        raise RuntimeError("boom")

    monkeypatch.setattr(research_job, "run_research_pipeline_stream", exploding_pipeline)
    monkeypatch.setattr(research_job, "AsyncSessionLocal", session_factory)

    redis = FakeRedis()
    # Must not raise — a deterministic failure is persisted, not retried.
    await run_research_job({"redis": redis}, "NVDA", str(user.id), str(uuid.uuid4()))
    assert redis.published[-1][1] == STREAM_END


async def test_queued_research_returns_202_with_stream_url(
    client, dev_user, queued_mode, monkeypatch
):
    enqueued: list[tuple] = []

    class FakePool:
        async def enqueue_job(self, name, *args):
            enqueued.append((name, args))

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr("backend.api.routes_research.get_arq_pool", fake_get_pool)

    resp = await client.post("/api/research", json={"ticker": "NVDA"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["stream_url"] == f"/api/jobs/{body['report_id']}/stream"

    (name, args) = enqueued[0]
    assert name == "run_research_job"
    assert args[0] == "NVDA" and args[2] == body["report_id"]


async def test_job_stream_serves_snapshot_for_finished_report(
    client, db_session, dev_user, queued_mode
):
    from tests.test_api import seed_report

    report = await seed_report(db_session, dev_user.id)

    async with client.stream("GET", f"/api/jobs/{report.id}/stream") as resp:
        assert resp.status_code == 200
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "complete"
    assert events[0]["report"]["verdict"] == "BUY"
    assert "event: done" in raw


async def test_job_stream_is_tenant_scoped(client, db_session, queued_mode):
    from tests.test_api import seed_report

    stranger = User(email="stranger@example.com", plan="pro")
    db_session.add(stranger)
    await db_session.commit()
    report = await seed_report(db_session, stranger.id)

    resp = await client.get(f"/api/jobs/{report.id}/stream")
    assert resp.status_code == 404  # dev user doesn't own it


async def test_job_stream_404_when_queue_disabled(client, dev_user):
    resp = await client.get(f"/api/jobs/{uuid.uuid4()}/stream")
    assert resp.status_code == 404
