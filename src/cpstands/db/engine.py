"""Async database engine and session factory (ADR-011)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, pool_size: int = 10) -> AsyncEngine:
    """Create the async engine; pool size follows NFR-006."""
    return create_async_engine(database_url, pool_size=pool_size, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
