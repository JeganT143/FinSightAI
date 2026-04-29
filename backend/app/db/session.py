from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(settings.database_url, pool_pre_ping=True) # Connects to your DB URL, creates a pool of connections, and checks if they're alive before using them
SessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
) # A factory that creates new sessions (managers that hand out workers)        


async def get_session() -> AsyncSession: # a FastAPI dependency that gives you a session (a worker) whenever you need to talk to the database
    async with SessionLocal() as session:
        yield session


# Notes :
"""
1. Why this exists:
-------------------
Your app needs to talk to a database. But opening a brand new connection 
every time someone makes a request is like hiring a new employee every 
time a customer walks in, and firing them when they leave. That's slow 
and wasteful.
This code creates a connection pool (a team of standing employees) and 
a session factory (a manager who hands out workers when needed)



"""