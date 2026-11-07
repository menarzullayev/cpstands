from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from cpstands.__main__ import alembic_config
from cpstands.config import get_settings

DEFAULT_ADMIN_URL = "postgresql+asyncpg://cpstands:cpstands@127.0.0.1:5440/postgres"


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _admin_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)


@pytest.fixture
async def temp_database() -> AsyncIterator[str]:
    """Create an empty throw-away database and yield its async URL; drop it afterwards."""
    admin_url = _admin_url()
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    name = f"cpstands_test_{secrets.token_hex(6)}"
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:
        await admin.dispose()
        if os.environ.get("REQUIRE_DB") == "1":
            raise
        pytest.skip(f"PostgreSQL is not reachable ({type(exc).__name__}); set TEST_DATABASE_URL")
    url = admin_url.rsplit("/", 1)[0] + f"/{name}"
    try:
        yield url
    finally:
        async with admin.connect() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"
                ),
                {"name": name},
            )
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        await admin.dispose()


@pytest.fixture
async def migrated_database(temp_database: str) -> str:
    """A throw-away database with all migrations applied."""
    import asyncio

    await asyncio.to_thread(command.upgrade, alembic_config(temp_database), "head")
    return temp_database
