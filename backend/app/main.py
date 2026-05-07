from contextlib import asynccontextmanager

from app.api import routes_auth, routes_billing, routes_research
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import Base
from app.db.session import engine
from app.services.session_store import session_store
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await session_store.connect()
    yield
    # Shutdown
    await session_store.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(routes_auth.router)
app.include_router(routes_research.router, prefix="/api")
app.include_router(routes_billing.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "healthy"}
