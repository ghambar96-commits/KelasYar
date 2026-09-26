"""Async SQLAlchemy engine & session factory.

SQLite is used by default (zero-config development); switching to PostgreSQL
is only a matter of changing DATABASE_URL – the models are fully portable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

_engine_kwargs: dict = {}

if settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"timeout": 30}
    # In-memory SQLite needs a shared connection to be usable across sessions
    # (used by the test-suite).
    if ":memory:" in settings.database_url or settings.database_url.endswith("://"):
        _engine_kwargs["poolclass"] = StaticPool
        _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency – yields a scoped async session per request."""
    async with AsyncSessionLocal() as session:
        yield session
