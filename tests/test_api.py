import json

from backend.db import crud
from tests.factories import make_critic, make_draft, make_specialist, make_traced_run


async def seed_report(db, user_id, ticker="NVDA"):
    report = await crud.create_report(db, user_id, ticker)
    run = make_traced_run("FundamentalsAgent", "research", make_specialist("FundamentalsAgent"))
    await crud.add_agent_run(db, report.id, run)
    await crud.complete_report(
        db,
        report,
        draft=make_draft(ticker=ticker),
        critic=make_critic(),
        revision_count=0,
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.02,
        latency_ms=38000,
    )
    return report


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_list_reports_empty(client):
    resp = await client.get("/api/reports")
    assert resp.status_code == 200
    assert resp.json() == {"reports": [], "total": 0, "limit": 20, "offset": 0}


async def test_list_reports_with_ticker_filter(client, db_session, dev_user):
    await seed_report(db_session, dev_user.id, "NVDA")
    await seed_report(db_session, dev_user.id, "AAPL")

    resp = await client.get("/api/reports")
    assert resp.json()["total"] == 2

    resp = await client.get("/api/reports", params={"ticker": "nvda"})
    body = resp.json()
    assert body["total"] == 1
    summary = body["reports"][0]
    assert summary["ticker"] == "NVDA"
    assert summary["verdict"] == "BUY"
    assert summary["overall_score"] == 7.0
    assert summary["cost_usd"] == 0.02


async def test_report_detail_includes_agent_runs(client, db_session, dev_user):
    report = await seed_report(db_session, dev_user.id)

    resp = await client.get(f"/api/reports/{report.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["report"]["verdict"] == "BUY"
    assert body["usage"]["cost_usd"] == 0.02
    assert len(body["agent_runs"]) == 1
    assert body["agent_runs"][0]["agent_name"] == "FundamentalsAgent"
    assert body["agent_runs"][0]["output"]["score"] == 7.0


async def test_report_detail_404(client):
    resp = await client.get("/api/reports/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_invalid_ticker_rejected(client):
    resp = await client.post("/api/research/stream", json={"ticker": "NOT-A-TICKER"})
    assert resp.status_code == 422


async def test_research_stream_emits_sse(client, session_factory, monkeypatch):
    """Stream endpoint contract: data: lines with JSON events, then a done event."""

    async def fake_pipeline(ticker, user_id, db, plan_limits=None):
        yield {"type": "start", "report_id": "x", "ticker": ticker}
        yield {"type": "complete", "report_id": "x", "ticker": ticker}

    monkeypatch.setattr("backend.api.routes_research.run_research_pipeline_stream", fake_pipeline)
    monkeypatch.setattr("backend.api.routes_research.AsyncSessionLocal", session_factory)

    async with client.stream("POST", "/api/research/stream", json={"ticker": "NVDA"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = "".join([chunk async for chunk in resp.aiter_text()])

    data_lines = [line for line in raw.splitlines() if line.startswith("data: ")]
    events = [json.loads(line[6:]) for line in data_lines]
    assert events[0]["type"] == "start"
    assert events[0]["ticker"] == "NVDA"
    assert events[1]["type"] == "complete"
    assert "event: done" in raw
