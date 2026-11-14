"""Live standings: scheduling, in-place edits, limits and failure handling (real PostgreSQL)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import EditMessageText
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import live
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import ContestPhase, FullStandings
from cpstands.i18n import I18n
from cpstands.services.standings import StandingsService
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource, make_standings
from tests.support.telegram import FakeSession, make_bot

CHAT = -1001
OTHER_CHAT = -1002
BASE = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
METHOD = EditMessageText(text="x")


def running(contest_id: int = 1970, **kwargs: object) -> FullStandings:
    kwargs.setdefault("rows", 60)
    kwargs.setdefault("problems", 5)
    return make_standings(contest_id=contest_id, phase=ContestPhase.CODING, **kwargs)  # type: ignore[arg-type]


@dataclass
class Rig:
    updater: live.LiveUpdater
    source: FakeSource
    session: FakeSession
    sessions: async_sessionmaker[AsyncSession]
    clock: FakeClock

    def edits(self) -> list[dict[str, object]]:
        return self.session.sent("EditMessageText")

    async def register(
        self, chat_id: int = CHAT, contest_id: int = 1970, message_id: int = 500
    ) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_chat(session, chat_id, "supergroup")
            await repos.register_live_message(
                session, chat_id, "codeforces", contest_id, message_id, max_live=3
            )

    async def rows(self) -> list[tuple[int, int, str]]:
        async with self.sessions() as session:
            result = await session.execute(
                text("select chat_id, contest_id, state from standings_messages order by 1, 2")
            )
            return [(int(a), int(b), str(c)) for a, b, c in result.all()]


@pytest.fixture
async def rig(migrated_database: str) -> AsyncIterator[Rig]:
    engine = create_engine(migrated_database, pool_size=3)
    sessions = create_session_factory(engine)
    clock = FakeClock()
    source = FakeSource([], standings={1970: running()})
    fake = FakeSession()
    now = lambda: BASE + timedelta(seconds=clock.now - 1000)  # noqa: E731
    service = StandingsService(source, clock=clock.monotonic, now=now)  # type: ignore[arg-type]
    updater = live.LiveUpdater(
        make_bot(fake), sessions, service, I18n(), clock=clock.monotonic, now=now, sleep=clock.sleep
    )
    yield Rig(updater, source, fake, sessions, clock)
    await engine.dispose()


def test_fetch_delay_follows_the_cache_expiry() -> None:
    base = running()
    assert live.fetch_delay(base, BASE) == 60.0
    assert live.fetch_delay(replace(base, expires_at=BASE + timedelta(seconds=30)), BASE) == 31.0
    assert live.fetch_delay(replace(base, expires_at=BASE - timedelta(seconds=30)), BASE) == 2.0
    assert live.fetch_delay(replace(base, expires_at=BASE + timedelta(hours=1)), BASE) == 120.0


def test_digest_ignores_the_status_line_but_not_the_table() -> None:
    a = "<h1>C</h1><p>updated 12:00</p><table><tr><td>1</td></tr></table>"
    b = "<h1>C</h1><p>updated 12:01</p><table><tr><td>1</td></tr></table>"
    c = "<h1>C</h1><p>updated 12:01</p><table><tr><td>2</td></tr></table>"
    assert live.table_digest(a) == live.table_digest(b)
    assert live.table_digest(a) != live.table_digest(c)


async def test_a_changed_table_is_edited_in_place_and_an_unchanged_one_is_not(rig: Rig) -> None:
    await rig.register()
    await rig.updater.tick()
    assert len(rig.edits()) == 1
    first = rig.edits()[0]
    assert (first["chat_id"], first["message_id"]) == (CHAT, 500)
    assert first["rich_message"]["html"].startswith("<h1>Test Contest</h1>")  # type: ignore[index]

    rig.clock.advance(61)
    await rig.updater.tick()
    assert len(rig.edits()) == 1  # same table, clock still fresh enough

    rig.source.standings[1970] = running(rows=61)  # the table changed
    rig.clock.advance(61)
    await rig.updater.tick()
    assert len(rig.edits()) == 2


async def test_the_clock_is_refreshed_even_when_the_table_is_unchanged(rig: Rig) -> None:
    await rig.register()
    await rig.updater.tick()
    rig.clock.advance(live.STALE_TIME_S + 1)
    await rig.updater.tick()
    assert len(rig.edits()) == 2


async def test_fetches_follow_the_schedule_not_the_tick_rate(rig: Rig) -> None:
    await rig.register()
    for _ in range(5):
        await rig.updater.tick()
        rig.clock.advance(live.TICK_S)
    assert rig.source.full_fetches == 1
    rig.clock.advance(60)
    await rig.updater.tick()
    assert rig.source.full_fetches == 2


async def test_many_chats_share_one_fetch(rig: Rig) -> None:
    await rig.register(CHAT, message_id=1)
    await rig.register(OTHER_CHAT, message_id=2)
    await rig.updater.tick()
    assert rig.source.full_fetches == 1
    assert sorted(int(e["chat_id"]) for e in rig.edits()) == [OTHER_CHAT, CHAT]  # type: ignore[call-overload]


async def test_the_readers_page_is_kept(rig: Rig) -> None:
    await rig.register()
    async with rig.sessions() as session, session.begin():
        assert await repos.set_live_pages(session, CHAT, "codeforces", 1970, 500, 2, 0)
        assert not await repos.set_live_pages(session, CHAT, "codeforces", 1970, 999, 0, 0)
    await rig.updater.tick()
    html = str(rig.edits()[0]["rich_message"]["html"])  # type: ignore[index]
    assert "<td>51</td>" in html
    assert "<td>1</td><td>" not in html.split("</tr>")[1]


async def test_a_finished_contest_gets_a_final_edit_and_stops(rig: Rig) -> None:
    await rig.register()
    await rig.updater.tick()
    rig.source.standings[1970] = make_standings(contest_id=1970, rows=60, problems=5)  # FINISHED
    rig.clock.advance(61)
    await rig.updater.tick()
    assert len(rig.edits()) == 2
    assert "Yakunlangan" in str(rig.edits()[-1]["rich_message"]["html"])  # type: ignore[index]
    assert await rig.rows() == [(CHAT, 1970, "frozen")]
    fetches = rig.source.full_fetches
    rig.clock.advance(600)
    await rig.updater.tick()
    assert rig.source.full_fetches == fetches


async def test_source_errors_back_off_and_recover(rig: Rig) -> None:
    await rig.register()
    rig.source.fail = True
    await rig.updater.tick()
    assert rig.source.full_fetches == 1
    rig.clock.advance(live.ERROR_BACKOFF_START_S - 1)
    await rig.updater.tick()
    assert rig.source.full_fetches == 1  # still backing off
    rig.clock.advance(2)
    await rig.updater.tick()
    assert rig.source.full_fetches == 2
    rig.clock.advance(live.ERROR_BACKOFF_START_S * 2 + 1)  # the second failure doubled the wait
    rig.source.fail = False
    await rig.updater.tick()
    assert len(rig.edits()) == 1
    assert await rig.rows() == [(CHAT, 1970, "active")]


async def test_a_contest_that_disappears_is_orphaned(rig: Rig) -> None:
    await rig.register(contest_id=555)
    await rig.updater.tick()
    assert await rig.rows() == [(CHAT, 555, "orphaned")]
    assert not rig.edits()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (TelegramForbiddenError(METHOD, "Forbidden: bot was kicked"), "orphaned"),
        (TelegramBadRequest(METHOD, "Bad Request: message to edit not found"), "orphaned"),
        (TelegramBadRequest(METHOD, "Bad Request: message can't be edited"), "orphaned"),
        (TelegramBadRequest(METHOD, "Bad Request: message is not modified"), "active"),
        (TelegramBadRequest(METHOD, "Bad Request: something odd"), "active"),
    ],
)
async def test_edit_failures_are_classified(rig: Rig, error: Exception, state: str) -> None:
    await rig.register()
    rig.session.edit_error = error
    await rig.updater.tick()
    assert await rig.rows() == [(CHAT, 1970, state)]


async def test_flood_control_delays_the_next_fetch(rig: Rig) -> None:
    await rig.register()
    rig.session.edit_error = TelegramRetryAfter(METHOD, "Too Many Requests", 45)
    await rig.updater.tick()
    assert await rig.rows() == [(CHAT, 1970, "active")]
    rig.session.edit_error = None
    rig.clock.advance(40)
    await rig.updater.tick()
    assert rig.source.full_fetches == 1  # waits out retry_after plus a second
    rig.clock.advance(7)
    await rig.updater.tick()
    assert len(rig.edits()) == 2  # one refused attempt, one real edit


async def test_removed_chats_are_dropped(rig: Rig) -> None:
    await rig.register()
    async with rig.sessions() as session, session.begin():
        await repos.set_status(session, CHAT, "removed")
    await rig.updater.tick()
    assert not rig.edits()
    assert rig.source.full_fetches == 0  # nobody is listening, so nothing is fetched


async def test_edits_in_one_chat_are_spaced(rig: Rig) -> None:
    rig.source.standings[1971] = running(1971)
    await rig.register(contest_id=1970, message_id=1)
    await rig.register(contest_id=1971, message_id=2)
    await rig.updater.tick()
    assert len(rig.edits()) == 2
    assert sum(rig.clock.sleeps) >= live.MIN_EDIT_GAP_S - 0.001


async def test_a_chat_keeps_at_most_three_live_messages_and_new_ones_replace_old(
    rig: Rig,
) -> None:
    async with rig.sessions() as session, session.begin():
        await repos.upsert_chat(session, CHAT, "supergroup")
    for contest_id, message_id in ((1, 101), (2, 102), (3, 103), (4, 104), (4, 999)):
        async with rig.sessions() as session, session.begin():
            await repos.register_live_message(
                session, CHAT, "codeforces", contest_id, message_id, max_live=3
            )
    assert await rig.rows() == [
        (CHAT, 1, "frozen"),
        (CHAT, 2, "active"),
        (CHAT, 3, "active"),
        (CHAT, 4, "active"),
    ]
    async with rig.sessions() as session:
        messages = await repos.live_messages(session, "codeforces", 4)
    assert [m.message_id for m in messages] == [999]  # the newest message took over


def test_html_in_status_is_not_confused_with_the_table() -> None:
    page = "<h1>A</h1><p>x</p><table><tr><td>1</td></tr></table><blockquote>f</blockquote>"
    stripped = re.sub(r"<p>.*?</p>", "", page, count=1)
    assert "<p>" not in stripped
    assert live.table_digest(page) == live.table_digest(page.replace("<p>x</p>", "<p>y</p>"))


async def test_link_only_chats_get_no_callback_buttons(rig: Rig) -> None:
    """A comment table lives in a chat whose taps are never answered: links only."""
    await rig.register()
    await rig.updater.tick()
    normal = rig.edits()[-1]["reply_markup"]["inline_keyboard"]  # type: ignore[index]
    assert any("callback_data" in b for row in normal for b in row)  # the control

    rig.updater._link_only = frozenset({CHAT})
    rig.source.standings[1970] = running(rows=61)
    rig.clock.advance(61)
    await rig.updater.tick()
    linked = rig.edits()[-1]["reply_markup"]["inline_keyboard"]  # type: ignore[index]
    buttons = [b for row in linked for b in row]
    assert buttons
    assert all("url" in b and "callback_data" not in b for b in buttons)
