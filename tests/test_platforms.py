"""kep.uz next to Codeforces: prefixes, links, callbacks and the multi-platform watch list."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import platforms
from cpstands.bot import rank_view, standings_view
from cpstands.bot.alerts import render_alerts
from cpstands.bot.rating_card import app_route
from cpstands.bot.summary import parse_target, render_summary
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.i18n import I18n
from cpstands.services.watchlist import WatchlistService, by_platform, parse_handles
from tests.support.sources import FakeSource

CHAT = -1001234567890
OTHER = -1009999999999
CHANNEL = -1004388100807
KEP = platforms.PLATFORMS[platforms.KEP]
CF = platforms.DEFAULT


class FakeKep(FakeSource):
    platform = platforms.KEP


# --- prefixes and links ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "platform", "rest"),
    [
        ("tourist", "codeforces", "tourist"),
        ("kep:alice", "kep", "alice"),
        ("KEP:Alice", "kep", "Alice"),
        ("https://kep.uz/users/alice", "kep", "alice"),
        ("kep.uz/users/user/alice", "kep", "alice"),
        ("https://codeforces.com/profile/Petr", "codeforces", "Petr"),
        ("kepler", "codeforces", "kepler"),  # a handle that merely starts with "kep"
    ],
)
def test_split_reads_the_platform(token: str, platform: str, rest: str) -> None:
    site, bare = platforms.split(token)
    assert (site.name, bare) == (platform, rest)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1970", ("codeforces", 1970)),
        ("kep:504", ("kep", 504)),
        ("https://kep.uz/competitions/contests/contest/504/standings", ("kep", 504)),
        ("https://codeforces.com/contest/1970", ("codeforces", 1970)),
        ("kep:", None),
        ("kep:abc", None),
        ("0", None),
        ("12345678", None),
        ("", None),
    ],
)
def test_parse_contest(text: str, expected: tuple[str, int] | None) -> None:
    found = platforms.parse_contest(text)
    assert (None if found is None else (found[0].name, found[1])) == expected


def test_links_and_slugs() -> None:
    assert KEP.contest_url(504) == "https://kep.uz/competitions/contests/contest/504"
    assert KEP.problem_url(504, "C1").endswith("/contest/504/problem/C1")
    assert KEP.profile_url("alice") == "https://kep.uz/users/alice"
    assert (KEP.shown("alice"), KEP.slug(504)) == ("kep:alice", "kep504")
    assert (CF.shown("tourist"), CF.slug(1970)) == ("tourist", "1970")
    assert (app_route(KEP, "alice"), app_route(CF, "tourist")) == (
        "kprofile_alice",
        "profile_tourist",
    )


def test_parse_handles_keeps_prefixes_and_groups_by_platform() -> None:
    parsed = parse_handles("tourist kep:alice https://kep.uz/users/Bob KEP:ALICE kep:bad!")
    assert parsed.valid == ("tourist", "kep:alice", "kep:Bob")
    assert parsed.invalid == ("kep:bad!",)
    assert by_platform(parsed.valid) == {"codeforces": ["tourist"], "kep": ["alice", "Bob"]}


def test_standings_callbacks_carry_the_platform() -> None:
    data = standings_view.callback(504, 1, 0, "friends", platform="kep")
    assert data == "st:kep504:1:0:f"
    assert standings_view.parse_target(data.split(":")[1]) == (KEP, 504)
    # The old Codeforces form (already sent in chats) still reads as Codeforces.
    assert standings_view.callback(1970, 0, 0) == "st:1970:0:0:a"
    assert standings_view.parse_target("1970") == (CF, 1970)
    assert standings_view.parse_target("kepx") is None
    assert standings_view.parse_target("x1") is None


def test_rank_callbacks_carry_the_platform() -> None:
    assert rank_view.callback(2, refresh=True, site=KEP) == "rk:2:r:kep"
    assert rank_view.platform_of(["rk", "2", "r", "kep"]) == "kep"
    assert rank_view.platform_of(["rk", "2", "r"]) == "codeforces"
    assert rank_view.callback(0) == "rk:0"


def test_summary_targets() -> None:
    assert parse_target("") == (CF, None)
    assert parse_target("kep") == (KEP, None)
    assert parse_target("kep:504") == (KEP, 504)
    assert parse_target("1970") == (CF, 1970)
    assert parse_target("nonsense") is None


# --- rendering ---------------------------------------------------------------------------


def _chat() -> repos.ChatRecord:
    return repos.ChatRecord(
        chat_id=CHAT,
        chat_type="supergroup",
        status="active",
        language="en",
        time_zone="UTC",
        tone="neutral",
        reminder_offsets=(60,),
        alerts_enabled=True,
    )


def test_kep_alerts_link_to_kep() -> None:
    alert = repos.ClaimedAlert(
        id=1,
        chat_id=CHAT,
        event_key="kep|504|alice|A|solve|60",
        payload={
            "kind": "solve",
            "platform": "kep",
            "handle": "alice",
            "contest_id": 504,
            "contest_name": "KEP Contest #23",
            "problem": "A",
            "problem_name": "Sum",
            "time_s": 60,
            "v": 0,
            "at": datetime.now(UTC).isoformat(),
        },
        attempts=1,
    )
    [message] = render_alerts(I18n(), _chat(), [alert])
    assert "https://kep.uz/competitions/contests/contest/504" in message
    assert "https://kep.uz/users/alice" in message
    assert "kep:alice" in message
    assert "codeforces.com" not in message


def test_kep_summary_links_to_kep() -> None:
    payload = {
        "kind": "summary",
        "platform": "kep",
        "contest_id": 504,
        "contest_name": "KEP Contest #23",
        "participants": 60,
        "rated": True,
        "results": [{"handle": "alice", "rank": 3, "solved": 4, "old": 1500, "new": 1550}],
    }
    text_, markup = render_summary(I18n(), _chat(), payload)
    assert "https://kep.uz/users/alice" in text_
    assert "codeforces.com" not in text_
    urls = [b.url for row in markup.inline_keyboard for b in row if b.url]
    assert urls == [
        "https://kep.uz/competitions/contests/contest/504/standings",
        "https://t.me/cpstandsbot?startapp=standings_kep504",
    ]


# --- the database: watch list and reminders ----------------------------------------------


@pytest.fixture
async def sessions(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(migrated_database, pool_size=3)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await repos.upsert_chat(session, CHAT, "supergroup")
        await repos.upsert_chat(session, OTHER, "supergroup")
        await repos.upsert_chat(session, CHANNEL, "channel")
        await session.execute(text("UPDATE chats SET status = 'active'"))
    yield factory
    await engine.dispose()


async def test_watch_list_keeps_platforms_apart(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    service = WatchlistService(
        sessions,
        FakeSource(["tourist", "alice"]),  # type: ignore[arg-type]
        extra={"kep": FakeKep(["alice", "Bob"])},  # type: ignore[dict-item]
    )
    result = await service.add(CHAT, "tourist kep:ALICE kep:bob kep:ghost")
    assert result.added == ("tourist", "kep:alice", "kep:Bob")
    assert result.unknown == ("kep:ghost",)
    assert await service.list(CHAT) == ["tourist"]  # Codeforces only, as before
    assert await service.list(CHAT, "kep") == ["alice", "Bob"]
    assert await service.list_all(CHAT) == ["tourist", "kep:alice", "kep:Bob"]

    # The same name on Codeforces is another person: removing kep:alice keeps it there.
    await service.add(CHAT, "alice")
    removed = await service.remove(CHAT, "kep:alice kep:nobody")
    assert removed.removed == ("kep:alice",)
    assert removed.not_found == ("kep:nobody",)
    assert await service.list(CHAT) == ["alice", "tourist"]


async def test_a_platform_without_a_source_is_unknown(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    service = WatchlistService(sessions, FakeSource(["tourist"]))  # type: ignore[arg-type]
    result = await service.add(CHAT, "kep:alice")
    assert result.unknown == ("kep:alice",)
    assert await service.list_all(CHAT) == []


async def test_kep_reminders_go_only_to_followers_and_channels(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        await repos.upsert_contest(
            session, "kep", 504, "KEP Contest #23", "BEFORE", now + timedelta(days=1), 9000
        )
        await repos.add_handles(session, CHAT, "kep", {"alice": "alice"})
        planned = await repos.plan_reminders(session, "kep", now=now, followers_only=True)
        rows = await session.execute(
            text("SELECT DISTINCT chat_id FROM reminders WHERE platform = 'kep'")
        )
        chats = {int(r[0]) for r in rows.all()}
    assert planned > 0
    assert chats == {CHAT, CHANNEL}  # OTHER follows nobody on kep.uz


async def test_without_followers_only_every_chat_is_reminded(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    """The control for the test above: the filter, not the data, keeps OTHER out."""
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        await repos.upsert_contest(
            session, "kep", 504, "KEP Contest #23", "BEFORE", now + timedelta(days=1), 9000
        )
        await repos.plan_reminders(session, "kep", now=now)
        rows = await session.execute(
            text("SELECT DISTINCT chat_id FROM reminders WHERE platform = 'kep'")
        )
        assert {int(r[0]) for r in rows.all()} == {CHAT, OTHER, CHANNEL}
