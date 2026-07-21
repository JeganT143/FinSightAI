"""Concierge routes (SAAS §8.8): conversations + SSE message turns."""

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.db.models import Conversation, Message, User
from backend.db.session import AsyncSessionLocal, get_db
from backend.pipeline.concierge_turn import run_concierge_turn

router = APIRouter(prefix="/api/conversations", tags=["concierge"])


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


@router.post("")
async def create_conversation(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    await db.flush()
    return {"id": str(conversation.id), "title": conversation.title}


@router.get("")
async def list_conversations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    rows = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.user_id == user.id, Conversation.archived_at.is_(None))
                .order_by(Conversation.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return {
        "conversations": [
            {"id": str(c.id), "title": c.title, "created_at": c.created_at.isoformat()}
            for c in rows
        ]
    }


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
        )
        .scalars()
        .all()
    )
    return {
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "linked_report_id": str(m.linked_report_id) if m.linked_report_id else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
    }


@router.post("/{conversation_id}/messages/stream")
async def message_stream(
    conversation_id: uuid.UUID,
    request: MessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Ownership check up front so a 404 happens before the stream starts.
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def generator() -> AsyncGenerator[str]:
        async with AsyncSessionLocal() as turn_db:
            turn_user = await turn_db.get(User, user.id)
            assert turn_user is not None
            try:
                async for event in run_concierge_turn(
                    turn_db, turn_user, conversation_id, request.content
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except LookupError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
            except Exception:
                # Same sanitization contract as the research stream (ADR-12).
                yield f"data: {json.dumps({'type': 'error', 'message': 'Concierge turn failed'})}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
