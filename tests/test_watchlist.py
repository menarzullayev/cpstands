from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.services.watchlist import WatchlistService, parse_handles
from cpstands.sources.base import RetryableSourceError
from tests.support.sources import FakeSource

CHAT = -1001234567890


@pytest.fixture
async def sessions(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(migrated_database, pool_size=3)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await repos.upsert_chat(session, CHAT, "supergroup")
    yield factory
    await engine.dispose()


def _service(
    sessions: async_sessionmaker[AsyncSession], source: FakeSource, limit: int = 100
) -> WatchlistService:
    return WatchlistService(sessions, source, limit=limit)  # type: ignore[arg-type]


def test_parse_splits_on_commas_spaces_and_lines() -> None:
    parsed = parse_handles("tourist, jiangly\nPetr;@Um_nik  tourist")
    assert parsed.valid == ("tourist", "jiangly", "Petr", "Um_nik")
    assert not parsed.invalid
    assert not parsed.truncated


def test_parse_accepts_profile_links() -> None:
    parsed = parse_handles("https://codeforces.com/profile/tourist codeforces.com/profile/Petr/")
    assert parsed.valid == ("tourist", "Petr")


def test_parse_flags_invalid_tokens_and_enforces_the_input_cap() -> None:
    parsed = parse_handles("ok bad!name " + "x" * 30)
    assert parsed.valid == ("ok",)
    assert len(parsed.invalid) == 2
    many = parse_handles(" ".join(f"user{i}" for i in range(150)), max_items=100)
    assert len(many.valid) == 100
    assert many.truncated


async def test_add_list_and_remove_round_trip(sessions: async_sessionmaker[AsyncSession]) -> None:
    service = _service(sessions, FakeSource(["tourist", "jiangly", "Petr"]))
    result = await service.add(CHAT, "TOURIST, jiangly, nobody, bad!")
    assert result.added == ("tourist", "jiangly")
    assert result.unknown == ("nobody",)
    assert result.invalid == ("bad!",)
    assert await service.list(CHAT) == ["jiangly", "tourist"]

    again = await service.add(CHAT, "tourist Petr")
    assert again.already == ("tourist",)
    assert again.added == ("Petr",)

    removed = await service.remove(CHAT, "JIANGLY ghost")
    assert removed.removed == ("jiangly",)
    assert removed.not_found == ("ghost",)
    assert await service.list(CHAT) == ["Petr", "tourist"]


async def test_limit_is_enforced_and_reported(sessions: async_sessionmaker[AsyncSession]) -> None:
    names = [f"user{i}" for i in range(5)]
    service = _service(sessions, FakeSource(names), limit=3)
    result = await service.add(CHAT, " ".join(names))
    assert result.added == ("user0", "user1", "user2")
    assert result.over_limit == ("user3", "user4")
    assert len(await service.list(CHAT)) == 3


async def test_source_failure_changes_nothing(sessions: async_sessionmaker[AsyncSession]) -> None:
    service = _service(sessions, FakeSource(["tourist"], fail=True))
    with pytest.raises(RetryableSourceError):
        await service.add(CHAT, "tourist")
    assert await service.list(CHAT) == []


async def test_nothing_valid_does_not_call_the_source(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    source = FakeSource(["tourist"])
    result = await _service(sessions, source).add(CHAT, "!!! ???")
    assert source.calls == 0
    assert result.invalid == ("!!!", "???")
    assert not result.added


async def test_concurrent_adds_never_exceed_the_limit(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    import asyncio

    names = [f"user{i}" for i in range(10)]
    service = _service(sessions, FakeSource(names), limit=4)
    await asyncio.gather(*(service.add(CHAT, n) for n in names))
    assert len(await service.list(CHAT)) == 4


async def test_chat_upsert_reopens_removed_chat_and_keeps_active(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session, session.begin():
        await repos.set_status(session, CHAT, "removed")
        reopened = await repos.upsert_chat(session, CHAT, "supergroup")
        assert reopened.status == "onboarding"
        await repos.set_status(session, CHAT, "active")
        kept = await repos.upsert_chat(session, CHAT, "supergroup")
        assert kept.status == "active"


async def test_the_default_limit_is_200(sessions: async_sessionmaker[AsyncSession]) -> None:
    names = [f"u{i}" for i in range(201)]
    service = WatchlistService(sessions, FakeSource(names))  # type: ignore[arg-type]
    first = await service.add(CHAT, " ".join(names[:150]))
    assert len(first.added) == 150
    second = await service.add(CHAT, " ".join(names[150:]))
    assert len(second.added) == 50  # 200 in total
    assert second.over_limit == ("u200",)  # the 201st is refused
    assert len(await service.list(CHAT)) == 200
