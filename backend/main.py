from dotenv import load_dotenv

# Load .env before anything imports OpenAI-dependent modules
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.api.routes_research import router  # noqa: E402
from backend.core.config import settings  # noqa: E402

app = FastAPI(
    title=settings.app_name, version=settings.app_version, debug=settings.debug
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
