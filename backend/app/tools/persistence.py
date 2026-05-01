from dataclasses import dataclass
from uuid import UUID

from agents import RunContextWrapper, function_tool
from app.db.models import ResearchArtifact
from app.db.session import SessionLocal
from app.schemas.research import ResearchReport


@dataclass
class AgentCtx:
    """The "context" object the SDK threads through every run.
    Anything an agent or tool needs that should NOT be in the prompt goes here.
    user identities, database sessions, etc.
    """

    user_id: UUID
    session_id: UUID
    request_id: str


@function_tool
async def save_artifact(
    ctx: RunContextWrapper[AgentCtx], report: ResearchReport
) -> str:
    """Persists a  finised research report. returns the artifact ID"""

    async with SessionLocal() as db:
        art = ResearchArtifact(
            session_id=ctx.context.session_id,
            ticker=report.ticker,
            summary=report.summary,
            payload=report.model.dump(),
        )

        db.add(art)
        await db.commit()
        return str(art.id)
