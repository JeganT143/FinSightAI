import os
from dotenv import load_dotenv

# Load .env before anything else imports OpenAI
load_dotenv()

from fastapi import FastAPI
from backend.core.config import settings
from backend.api.routes_research import router

app = FastAPI(
    title=settings.app_name, version=settings.app_version, debug=settings.debug
)

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
