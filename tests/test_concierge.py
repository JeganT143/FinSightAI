"""Concierge turn tests (SAAS §8-9): refusal path, persistence, isolation.

The refusal path is proven LLM-free: traced_run is patched to explode, so a
single advice message reaching the agent fails the test loudly.
"""

import uuid

import pytest
from sqlalchemy import select

from backend.concierge.refusals import ADVICE_REFUSAL_TEXT
from backend.db.models import AuditLog, Conversation, Message, User
from backend.pipeline import concierge_turn as turn_module
from backend.pipeline.concierge_turn import run_concierge_turn
from backend.schemas.concierge import ConciergeTurn
from tests.factories import make_traced_run


@pytest.fixture
def agent_must_not_run(monkeypatch):
    async def exploding(*args, **kwargs):
        raise AssertionError("concierge_agent must not be invoked for refused intents")

    monkeypatch.setattr(turn_module, "traced_run", exploding)


@pytest.fixture
async def conversation(db_session, dev_user):
    conv = Conversation(user_id=dev_user.id)
    db_session.add(conv)
    await db_session.commit()
    return conv


async def collect(db, user, conversation_id, message):
    return [e async for e in run_concierge_turn(db, user, conversation_id, message)]


async def test_advice_request_gets_fixed_refusal_and_audit_row(
    db_session, dev_user, conversation, agent_must_not_run
):
    events = await collect(db_session, dev_user, conversation.id, "Should I buy NVDA?")

    assert events == [
        {"type": "refusal", "content": ADVICE_REFUSAL_TEXT, "intent": "advice_request"}
    ]

    # Both sides of the exchange persisted; refusal text is the verbatim constant.
    messages = (
        (await db_session.execute(select(Message).order_by(Message.created_at))).scalars().all()
    )
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].content == ADVICE_REFUSAL_TEXT

    # Independent compliance trail (SAAS §9).
    audit = (await db_session.execute(select(AuditLog))).scalar_one()
    assert audit.event_type == "advice_refusal"
    assert audit.user_id == dev_user.id


async def test_normal_turn_persists_and_links_report(
    db_session, dev_user, conversation, monkeypatch
):
    linked = str(uuid.uuid4())

    async def canned_run(agent, input_text, phase):
        assert phase == "concierge"
        return make_traced_run(
            "ConciergeAgent",
            phase,
            ConciergeTurn(
                content="NVDA scored 7.7 overall.",
                tool_calls_made=["search_past_reports", "get_report"],
                linked_report_id=linked,
            ),
        )

    monkeypatch.setattr(turn_module, "classify_intent", lambda m: _as_async("follow_up"))
    monkeypatch.setattr(turn_module, "traced_run", canned_run)

    events = await collect(db_session, dev_user, conversation.id, "what did NVDA score?")

    assert [e["type"] for e in events] == ["thinking", "message"]
    final = events[-1]
    assert final["linked_report_id"] == linked
    assert final["usage"]["cost_usd"] > 0  # chat turns are cost-tracked like agents

    messages = (
        (await db_session.execute(select(Message).order_by(Message.created_at))).scalars().all()
    )
    assert messages[-1].linked_report_id == uuid.UUID(linked)
    # First message becomes the conversation title.
    refreshed = await db_session.get(Conversation, conversation.id)
    assert refreshed.title == "what did NVDA score?"


async def test_conversation_isolation(db_session, dev_user, agent_must_not_run):
    other = User(email="other@example.com", plan="pro")
    db_session.add(other)
    await db_session.flush()
    foreign = Conversation(user_id=other.id)
    db_session.add(foreign)
    await db_session.commit()

    with pytest.raises(LookupError):
        await collect(db_session, dev_user, foreign.id, "hello")


async def test_conversation_routes_are_tenant_scoped(client, db_session, dev_user):
    other = User(email="other2@example.com", plan="pro")
    db_session.add(other)
    await db_session.flush()
    foreign = Conversation(user_id=other.id)
    db_session.add(foreign)
    await db_session.commit()

    resp = await client.get(f"/api/conversations/{foreign.id}/messages")
    assert resp.status_code == 404

    created = await client.post("/api/conversations")
    assert created.status_code == 200
    listed = await client.get("/api/conversations")
    ids = [c["id"] for c in listed.json()["conversations"]]
    assert created.json()["id"] in ids
    assert str(foreign.id) not in ids


def _as_async(value):
    async def _coro(*args, **kwargs):
        return value

    return _coro()
