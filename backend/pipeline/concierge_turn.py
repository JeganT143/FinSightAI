"""One Concierge turn (SAAS §8.7): classify -> refuse-or-route -> persist.

Every non-refused turn is a traced_run, so chat costs land in agent_runs
exactly like pipeline agents' do. Refusals never reach the LLM at all — a
fixed string plus an AuditLog row (SAAS §9), at zero token cost.
"""

import logging
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.concierge import concierge_agent
from backend.concierge.classifier import classify_intent
from backend.concierge.refusals import ADVICE_REFUSAL_TEXT
from backend.db.models import AuditLog, Conversation, Message, User
from backend.pipeline.tracing import traced_run
from backend.schemas.concierge import ConciergeTurn
from backend.tools.concierge_tools import current_user_id_var

logger = logging.getLogger(__name__)

_HISTORY_TURNS = 10


async def _transcript(db: AsyncSession, conversation_id: uuid.UUID, latest: str) -> str:
    rows = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(_HISTORY_TURNS)
            )
        )
        .scalars()
        .all()
    )
    lines = [f"{m.role}: {m.content}" for m in reversed(rows)]
    lines.append(f"user: {latest}")
    return "\n".join(lines)


async def run_concierge_turn(
    db: AsyncSession, user: User, conversation_id: uuid.UUID, message: str
) -> AsyncGenerator[dict]:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        # Same isolation rule as reports (SAAS §5): absence and denial look identical.
        raise LookupError("conversation not found")

    intent = await classify_intent(message)
    db.add(Message(conversation_id=conversation_id, role="user", content=message))

    if intent == "advice_request":
        db.add(
            Message(conversation_id=conversation_id, role="assistant", content=ADVICE_REFUSAL_TEXT)
        )
        db.add(
            AuditLog(
                user_id=user.id,
                event_type="advice_refusal",
                event_metadata={"conversation_id": str(conversation_id), "message": message[:500]},
            )
        )
        await db.commit()
        yield {"type": "refusal", "content": ADVICE_REFUSAL_TEXT, "intent": intent}
        return

    yield {"type": "thinking", "intent": intent}

    transcript = await _transcript(db, conversation_id, message)
    token = current_user_id_var.set(user.id)
    try:
        run = await traced_run(concierge_agent, transcript, phase="concierge")
    finally:
        current_user_id_var.reset(token)

    turn: ConciergeTurn = run.output
    linked_id: uuid.UUID | None = None
    if turn.linked_report_id:
        try:
            linked_id = uuid.UUID(turn.linked_report_id)
        except ValueError:
            linked_id = None

    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=turn.content,
            tool_calls={"tools": turn.tool_calls_made},
            linked_report_id=linked_id,
        )
    )
    if conversation.title == "New conversation":
        conversation.title = message[:117] + "..." if len(message) > 120 else message
    await db.commit()

    yield {
        "type": "message",
        "content": turn.content,
        "intent": intent,
        "tool_calls_made": turn.tool_calls_made,
        "linked_report_id": str(linked_id) if linked_id else None,
        "usage": run.usage_event,
    }
