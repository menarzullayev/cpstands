"""Migration and schema-invariant tests (need PostgreSQL; see conftest)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cpstands.__main__ import alembic_config
from cpstands.db.schema import metadata

pytestmark = pytest.mark.db


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(migrated_database)
    yield eng
    await eng.dispose()


async def _tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    return names


async def test_migration_creates_every_table_of_the_schema(engine: AsyncEngine) -> None:
    assert set(metadata.tables) | {"alembic_version"} == await _tables(engine)


async def test_migrated_database_matches_schema_metadata(engine: AsyncEngine) -> None:
    def diff(connection: Connection) -> list[object]:
        context = MigrationContext.configure(connection)
        return list(compare_metadata(context, metadata))

    async with engine.connect() as connection:
        assert await connection.run_sync(diff) == []


async def test_downgrade_removes_all_tables(temp_database: str) -> None:
    config = alembic_config(temp_database)
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.downgrade, config, "base")
    eng = create_async_engine(temp_database)
    try:
        assert await _tables(eng) <= {"alembic_version"}
    finally:
        await eng.dispose()


async def test_upgrade_is_idempotent(temp_database: str) -> None:
    config = alembic_config(temp_database)
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.upgrade, config, "head")


async def _exec(engine: AsyncEngine, sql: str, **params: object) -> None:
    async with engine.begin() as connection:
        await connection.execute(text(sql), params)


async def _chat(engine: AsyncEngine, chat_id: int = 1) -> None:
    await _exec(engine, "INSERT INTO chats (chat_id, chat_type) VALUES (:i, 'group')", i=chat_id)


async def test_chat_defaults(engine: AsyncEngine) -> None:
    await _chat(engine)
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT tone, alerts_enabled, reminder_offsets, status FROM chats WHERE chat_id = 1"
                )
            )
        ).one()
    assert tuple(row) == ("playful", True, [1440, 60, 10], "onboarding")


@pytest.mark.parametrize(
    ("column", "value"),
    [("chat_type", "bot"), ("language", "de"), ("tone", "rude"), ("status", "zombie")],
)
async def test_chat_check_constraints_reject_bad_values(
    engine: AsyncEngine, column: str, value: str
) -> None:
    values = {"chat_type": "group", "language": "uz", "tone": "playful", "status": "active"}
    values[column] = value
    with pytest.raises(IntegrityError):
        await _exec(
            engine,
            "INSERT INTO chats (chat_id, chat_type, language, tone, status) "
            "VALUES (1, :chat_type, :language, :tone, :status)",
            **values,
        )


async def test_watch_list_rejects_duplicate_handles(engine: AsyncEngine) -> None:
    await _chat(engine)
    insert = (
        "INSERT INTO watched_handles (chat_id, platform, handle_key, handle_display) "
        "VALUES (1, 'codeforces', 'tourist', 'tourist')"
    )
    await _exec(engine, insert)
    with pytest.raises(IntegrityError):
        await _exec(engine, insert)


async def test_one_standings_message_per_chat_and_contest(engine: AsyncEngine) -> None:
    await _chat(engine)
    insert = "INSERT INTO standings_messages (chat_id, platform, contest_id) VALUES (1, 'codeforces', 2249)"
    await _exec(engine, insert)
    with pytest.raises(IntegrityError):
        await _exec(engine, insert)


async def test_one_reminder_per_offset(engine: AsyncEngine) -> None:
    await _chat(engine)
    insert = (
        "INSERT INTO reminders (chat_id, platform, contest_id, offset_min, due_at) "
        "VALUES (1, 'codeforces', 2249, 60, now())"
    )
    await _exec(engine, insert)
    with pytest.raises(IntegrityError):
        await _exec(engine, insert)


async def test_solve_event_key_is_unique(engine: AsyncEngine) -> None:
    insert = (
        "INSERT INTO solve_events (event_key, platform, contest_id, handle_key, problem, kind, occurred_at) "
        "VALUES ('cf|2249|a|A|solve|1', 'codeforces', 2249, 'a', 'A', 'solve', now())"
    )
    await _exec(engine, insert)
    with pytest.raises(IntegrityError):
        await _exec(engine, insert)


async def test_event_kind_is_checked(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        await _exec(
            engine,
            "INSERT INTO solve_events (event_key, platform, contest_id, handle_key, problem, kind, occurred_at) "
            "VALUES ('k', 'codeforces', 1, 'a', 'A', 'cheat', now())",
        )


async def test_a_chat_announces_an_event_at_most_once(engine: AsyncEngine) -> None:
    await _chat(engine)
    insert = (
        "INSERT INTO deliveries (chat_id, kind, event_key, payload) "
        "VALUES (1, 'alert', 'cf|2249|a|A|solve|1', '{}'::jsonb)"
    )
    await _exec(engine, insert)
    with pytest.raises(IntegrityError):
        await _exec(engine, insert)


async def test_deliveries_without_event_key_may_repeat(engine: AsyncEngine) -> None:
    await _chat(engine)
    insert = "INSERT INTO deliveries (chat_id, kind, payload) VALUES (1, 'standings', '{}'::jsonb)"
    await _exec(engine, insert)
    await _exec(engine, insert)


async def test_deleting_a_chat_removes_its_data(engine: AsyncEngine) -> None:
    await _chat(engine)
    await _exec(
        engine,
        "INSERT INTO watched_handles (chat_id, platform, handle_key, handle_display) "
        "VALUES (1, 'codeforces', 'a', 'a')",
    )
    await _exec(
        engine, "INSERT INTO deliveries (chat_id, kind, payload) VALUES (1, 'alert', '{}'::jsonb)"
    )
    await _exec(
        engine,
        "INSERT INTO standings_messages (chat_id, platform, contest_id) VALUES (1, 'codeforces', 1)",
    )
    await _exec(
        engine,
        "INSERT INTO reminders (chat_id, platform, contest_id, offset_min, due_at) "
        "VALUES (1, 'codeforces', 1, 10, now())",
    )
    await _exec(engine, "DELETE FROM chats WHERE chat_id = 1")
    async with engine.connect() as connection:
        for table in ("watched_handles", "deliveries", "standings_messages", "reminders"):
            count = (await connection.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
            assert count == 0, table


async def test_orphan_rows_are_rejected(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        await _exec(
            engine,
            "INSERT INTO deliveries (chat_id, kind, payload) VALUES (999, 'alert', '{}'::jsonb)",
        )


async def test_due_delivery_partial_index_exists(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        definition = (
            await connection.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'deliveries_due'")
            )
        ).scalar()
    assert definition is not None
    assert "WHERE" in definition
    assert "pending" in definition
    assert "batched" in definition


async def test_a_channel_chat_is_allowed(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO chats (chat_id, chat_type) VALUES (-1004388100807, 'channel')")
        )
        await conn.execute(text("DELETE FROM chats WHERE chat_id = -1004388100807"))
    await engine.dispose()
