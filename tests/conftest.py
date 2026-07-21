"""Unit-test fixtures: in-memory SQLite stands in for Postgres.

Only the tables without pgvector columns are created — filing_chunks needs the
vector type and is exercised against real Postgres (integration/live runs),
not here (ADR-9: unit tier must be free and dependency-less).
"""

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.db.models import (
    AgentRun,
    AuditLog,
    Conversation,
    Message,
    ResearchReport,
    Subscription,
    UsageCounter,
    User,
)
from backend.db.session import Base

TEST_TABLES = [
    User.__table__,
    ResearchReport.__table__,
    AgentRun.__table__,
    Subscription.__table__,
    UsageCounter.__table__,
    Conversation.__table__,
    Message.__table__,
    AuditLog.__table__,
]


@pytest_asyncio.fixture
async def db_engine():
    # StaticPool: one shared connection, so mid-pipeline commits don't hand us
    # a fresh (empty) in-memory database from the pool.
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=TEST_TABLES))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def dev_user(db_session):
    """The same user auth_mode="disabled" resolves to — seeded reports made
    with this id are visible through the API in tests."""
    user = User(email="dev@localhost", plan="pro")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def client(db_session):
    from backend.db.session import get_db
    from backend.main import app

    async def override_get_db():
        yield db_session
        await db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
