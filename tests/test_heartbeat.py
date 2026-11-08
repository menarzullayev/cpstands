"""The bot stores the Mini App API key and keeps a heartbeat for the status page."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db.engine import create_engine, create_session_factory
from cpstands.services.heartbeat import HEARTBEAT_KEY, Heartbeat, store_api_secret


@pytest.fixture
async def sessions(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(migrated_database, pool_size=2)
    yield create_session_factory(engine)
    await engine.dispose()


async def scalar(sessions: async_sessionmaker[AsyncSession], sql: str) -> object:
    async with sessions() as session:
        return (await session.execute(text(sql))).scalar_one_or_none()


async def test_the_token_is_stored_and_replaced(sessions: async_sessionmaker[AsyncSession]) -> None:
    assert await store_api_secret(sessions, "1:first")
    assert await store_api_secret(sessions, "1:second")
    value = await scalar(sessions, "SELECT value FROM private.app_secrets WHERE name = 'bot_token'")
    assert value == "1:second"


async def test_a_database_without_the_api_schema_is_reported_not_raised(
    sessions: async_sessionmaker[AsyncSession], capsys: pytest.CaptureFixture[str]
) -> None:
    async with sessions() as session, session.begin():
        await session.execute(text("DROP SCHEMA private CASCADE"))
    assert not await store_api_secret(sessions, "1:secret-value")
    out = capsys.readouterr()
    assert "secret-value" not in out.out + out.err


async def test_heartbeat_records_time_commit_and_start(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    clock = iter([1000.0, 1060.0, 1120.0])
    hb = Heartbeat(sessions, commit="abcdef0123456789", version="1.2.3", clock=lambda: next(clock))
    await hb.tick()
    await hb.tick()
    value = await scalar(sessions, f"SELECT value FROM runtime_state WHERE key = '{HEARTBEAT_KEY}'")
    assert value == {"at": 1120, "commit": "abcdef012345", "version": "1.2.3", "startedAt": 1000}
