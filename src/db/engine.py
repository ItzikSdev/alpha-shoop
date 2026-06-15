"""
Async SQLAlchemy engine and session factory.

Dev setup (creates tables automatically):
    python -c "import asyncio; from src.db.engine import create_tables; asyncio.run(create_tables())"

Production: use Alembic migrations instead of create_tables().
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/alphashoop",
)

# Pool config: keep small for the MCP server (single-process, low concurrency)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,        # set True during debugging to see SQL
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,  # drop stale connections before use
)

_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects usable after commit
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides a transactional DB session.

    Usage:
        async with get_session() as session:
            session.add(ProductMapping(...))
            await session.commit()
    """
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """
    Create all tables defined in Base.metadata (dev / first-run only).
    In production, use Alembic: `alembic upgrade head`
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Call at process shutdown to close the connection pool cleanly."""
    await engine.dispose()
