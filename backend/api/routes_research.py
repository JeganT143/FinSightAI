import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.schemas.research import ResearchRequest, ResearchResponse
from backend.pipeline.research import (
    run_research_pipeline,
    run_research_pipeline_stream,
)
from backend.db.session import get_db, AsyncSessionLocal
from backend.db import crud

router = APIRouter(prefix="/api", tags=["research"])


@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest, db: AsyncSession = Depends(get_db)):
    try:
        report, was_revised, report_id = await run_research_pipeline(request.ticker, db)
        return ResearchResponse(
            ticker=request.ticker,
            report=report,
            status="complete",
            was_revised=was_revised,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/stream")
async def research_stream(request: ResearchRequest):
    async def event_generator():
        # Create and manage session manually inside the generator
        # This ensures the session stays alive for the entire stream
        async with AsyncSessionLocal() as db:
            try:
                async for event in run_research_pipeline_stream(request.ticker, db):
                    yield f"data: {json.dumps(event)}\n\n"
                # Commit after stream completes
                await db.commit()
            except Exception as e:
                await db.rollback()
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/research/{report_id}")
async def get_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    report = await crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": str(report.id),
        "ticker": report.ticker,
        "status": report.status,
        "report": report.report_v2 or report.report_v1,
        "was_revised": report.was_revised,
        "critic_challenges_found": report.critic_challenges_found,
        "created_at": report.created_at.isoformat(),
        "completed_at": (
            report.completed_at.isoformat() if report.completed_at else None
        ),
    }
