import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before anything imports OpenAI-dependent modules
load_dotenv()

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from backend.api.middleware import RequestContextMiddleware  # noqa: E402
from backend.api.routes_account import router as account_router  # noqa: E402
from backend.api.routes_research import router  # noqa: E402
from backend.core.config import settings  # noqa: E402
from backend.core.logging import configure_logging  # noqa: E402
from backend.db.session import engine, get_db  # noqa: E402

configure_logging(settings.log_level, settings.log_format)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info(
        "%s v%s starting (models: specialists=%s, synthesizer=%s, critic=%s)",
        settings.app_name,
        settings.app_version,
        settings.specialist_model,
        settings.synthesizer_model,
        settings.critic_model,
    )
    if settings.auth_mode == "disabled" and not settings.debug:
        # Deliberately loud (SAAS §3): an unauthenticated instance with a live
        # OpenAI key must never be exposed publicly.
        logger.critical(
            "AUTH IS DISABLED (auth_mode=disabled) outside debug — every caller "
            "acts as the dev user. Never expose this instance publicly."
        )
    yield
    # Return pooled connections cleanly so Postgres doesn't log aborted sessions.
    await engine.dispose()
    logger.info("%s stopped", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last => outermost: request IDs and the error boundary wrap everything,
# CORS headers included.
app.add_middleware(RequestContextMiddleware)

app.include_router(router)
app.include_router(account_router)


@app.get("/health")
async def health() -> dict:
    """Liveness: process is up. No dependencies checked — a DB blip must not
    make an orchestrator restart the API container."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health/ready", response_model=None)
async def ready(db: AsyncSession = Depends(get_db)) -> JSONResponse | dict:
    """Readiness: can this instance actually serve? Fails when Postgres is
    unreachable, so load balancers / compose healthchecks stop routing to it."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed: database unreachable")
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ready", "database": "up"}
