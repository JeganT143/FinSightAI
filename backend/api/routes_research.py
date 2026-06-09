from fastapi import APIRouter, HTTPException
from backend.schemas.research import ResearchRequest, ResearchResponse
from backend.pipeline.research import run_research_pipeline

router = APIRouter(prefix="/api", tags=["research"])


@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    try:
        report, was_revised = await run_research_pipeline(request.ticker)
        return ResearchResponse(
            ticker=request.ticker,
            report=report,
            status="complete",
            was_revised=was_revised,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
