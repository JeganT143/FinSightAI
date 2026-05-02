from uuid import uuid4

from agents import Runner
from app.agents.triage import triage_agent
from app.core.security import current_user
from app.schemas.research import ResearchRequest
from app.services.session_store import get_session_store
from app.tools.persistence import AgentCtx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/stream", response_class=StreamingResponse)
async def research_stream(req: ResearchRequest, user=Depends(current_user)):
    session = await get_session_store().create_session(user_id=user.id)
    ctx = AgentCtx(
        user_id=user.id,
        session_id=session.id,
        request_id=str(uuid4()),
    )

    async def gen():
        prompt = f"""
        Research {req.ticker} for horizon {req.horizon} with focus on {req.question}.\
        """
        result = Runner.run_streamed(triage_agent, prompt, ctx)

        async for ev in result.stream_events():
            payload = _serialize(ev)
            if payload:
                yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


def _serialize(ev):
    if ev.type == "raw_response_event" and getattr(ev.data, "delta", None):
        return {"type": "token", "delta": ev.data.delta}
    if ev.type == "agent_updated_stream_event":
        return {"type": "handoff", "agent": ev.new_agent.name}
    if ev.type == "run_item_stream_event":
        item = ev.item
        if item.type == "tool_call_item":
            return {"type": "tool_call", "name": item.tool_name}
        if item.type == "tool_call_output_item":
            return {"type": "tool_result", "name": item.tool_name}
    return None
