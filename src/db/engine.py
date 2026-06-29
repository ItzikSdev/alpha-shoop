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

# Single shared database: everything (org agents, stores, traces AND product
# mappings) lives in ONE SQLite file — the same traces.db the rest of the system
# uses — so Linus, Grace and the dashboard all read/write the same place. Override
# with DATABASE_URL to point elsewhere (e.g. Postgres) if ever needed.
_TRACES_DB = os.getenv("TRACES_DB_PATH", "/app/data/traces.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{_TRACES_DB}")

if DATABASE_URL.startswith("sqlite"):
    # SQLite has no connection pool to size; allow cross-thread use (FastAPI + the
    # background heartbeat share the engine).
    engine = create_async_engine(
        DATABASE_URL, echo=False, connect_args={"check_same_thread": False},
    )
else:
    # Pool config for a real server DB (Postgres) — small, single-process.
    engine = create_async_engine(
        DATABASE_URL, echo=False, pool_size=5, max_overflow=2, pool_pre_ping=True,
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
