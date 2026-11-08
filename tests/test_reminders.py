"""Reminders: planning, at-most-once delivery, restarts, contest changes (real PostgreSQL)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import SendMessage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import reminders as rem
from cpstands.bot.scheduler import Scheduler
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import Contest, ContestPhase
from cpstands.i18n import I18n
from cpstands.services.contests import ContestService
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource
from tests.support.telegram import FakeSession, make_bot

CHAT = -1001
OTHER = -1002
START = datetime(2026, 11, 21, 14, 35, tzinfo=UTC)
METHOD = SendMessage(chat_id=1, text="x")


def contest(
    cid: int = 2287,
    *,
    starts: datetime = START,
    phase: ContestPhase = ContestPhase.BEFORE,
    name: str = "Codeforces Round (Div. 1)",
) -> Contest:
    return Contest("codeforces", cid, name, phase, "CF", starts, 7200)


@dataclass
class Rig:
    sessions: async_sessionmaker[AsyncSession]
    source: FakeSource
    fake: FakeSession
    clock: FakeClock
    now: datetime = field(default_factory=lambda: START - timedelta(hours=25))

    def at(self, moment: datetime) -> None:
        self.now = moment

    def build(self) -> Scheduler:
        """A fresh scheduler and service: this is what a process restart looks like."""
        service = ContestService(
            self.sessions,
            self.source,  # type: ignore[arg-type]
            now=lambda: self.now,
            clock=self.clock.monotonic,
        )
        sender = rem.ReminderSender(make_bot(self.fake), self.sessions, I18n())
        return Scheduler(
            self.sessions, service, sender, clock=self.clock.monotonic, now=lambda: self.now,
            sleep=self.clock.sleep,
        )  # fmt: skip

    async def add_chat(self, chat_id: int = CHAT, *, active: bool = True) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_chat(session, chat_id, "supergroup")
            await repos.set_language(session, chat_id, "en")
            await repos.set_time_zone(session, chat_id, "Asia/Tashkent")
            if active:
                await repos.set_status(session, chat_id, "active")

    async def reminders(self, chat_id: int = CHAT) -> dict[int, str]:
        async with self.sessions() as session:
            result = await session.execute(
                text("select offset_min, state from reminders where chat_id = :c order by 1 desc"),
                {"c": chat_id},
            )
            return {int(a): str(b) for a, b in result.all()}

    def sent(self) -> list[dict[str, object]]:
        return self.fake.sent()

    async def tick(self) -> int:
        self.clock.advance(1000)  # make the sync interval elapse so every tick re-reads the list
        return await self.build().tick()


@pytest.fixture
async def rig(migrated_database: str) -> AsyncIterator[Rig]:
    engine = create_engine(migrated_database, pool_size=4)
    sessions = create_session_factory(engine)
    source = FakeSource([], contests=[contest()])
    yield Rig(sessions, source, FakeSession(), FakeClock())
    await engine.dispose()


async def test_offsets_in_the_future_are_scheduled_and_past_ones_skipped(rig: Rig) -> None:
    await rig.add_chat()
    rig.at(START - timedelta(minutes=30))
    await rig.tick()
    assert await rig.reminders() == {1440: "skipped", 60: "skipped", 10: "scheduled"}


async def test_planning_is_idempotent_and_ignores_inactive_chats_and_far_contests(
    rig: Rig,
) -> None:
    await rig.add_chat()
    await rig.add_chat(OTHER, active=False)
    rig.source.contests.append(contest(9, starts=START + timedelta(days=40)))
    scheduler = rig.build()
    await scheduler.tick()
    first = await rig.reminders()
    await scheduler.tick()
    assert await rig.reminders() == first == {1440: "scheduled", 60: "scheduled", 10: "scheduled"}
    assert await rig.reminders(OTHER) == {}
    async with rig.sessions() as session:
        count = (await session.execute(text("select count(*) from reminders"))).scalar_one()
    assert count == 3  # nothing for the contest 40 days away or the unfinished chat


async def test_each_offset_is_sent_once_with_start_time_entities_and_buttons(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()  # 25 h before: nothing is due yet
    assert not rig.sent()

    rig.at(START - timedelta(hours=24) + timedelta(seconds=20))
    assert await rig.tick() == 1
    message = rig.sent()[-1]
    body = str(message["text"])
    assert "Codeforces Round (Div. 1)" in body
    assert "starts in 24 hours" in body
    unix = int(START.timestamp())
    assert f'<tg-time unix="{unix}" format="wDt">21.11 19:35</tg-time>' in body  # Tashkent
    assert f'<tg-time unix="{unix}" format="r">' in body
    buttons = [b for row in message["reply_markup"]["inline_keyboard"] for b in row]  # type: ignore[index]
    assert [b["url"] for b in buttons] == [
        "https://codeforces.com/contestRegistration/2287",
        "https://codeforces.com/contest/2287",
    ]
    preview: dict[str, object] = message["link_preview_options"]  # type: ignore[assignment]
    assert preview["is_disabled"] is True

    assert await rig.tick() == 0  # asking again changes nothing
    rig.at(START - timedelta(hours=1))
    assert await rig.tick() == 1
    rig.at(START - timedelta(minutes=10))
    assert await rig.tick() == 1
    assert [("24 hours" in str(m["text"]), "1 hour" in str(m["text"])) for m in rig.sent()] == [
        (True, False), (False, True), (False, False),
    ]  # fmt: skip
    assert "10 minutes" in str(rig.sent()[-1]["text"])
    assert await rig.reminders() == {1440: "sent", 60: "sent", 10: "sent"}


async def test_a_restart_never_repeats_a_reminder(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()  # planned a day ahead
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    assert await rig.build().tick() == 1
    for _ in range(3):
        assert await rig.build().tick() == 0  # three more "processes"
    assert len(rig.sent()) == 1


async def test_reminders_that_are_far_too_late_are_skipped_not_sent(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()  # planned while everything is still ahead
    rig.at(START - timedelta(hours=20))  # the bot was down; the 24 h moment passed 4 h ago
    assert await rig.tick() == 0
    assert (await rig.reminders())[1440] == "skipped"
    assert not rig.sent()


async def test_a_moved_contest_updates_unsent_reminders_and_tells_chats_already_warned(
    rig: Rig,
) -> None:
    await rig.add_chat()
    await rig.tick()  # planned a day ahead
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    assert await rig.tick() == 1  # CHAT is warned 24 hours ahead
    await rig.add_chat(OTHER)  # OTHER joins afterwards, so the 24 h moment is already behind it
    await rig.tick()
    assert (await rig.reminders(OTHER))[1440] == "skipped"
    rig.fake.calls.clear()

    new_start = START + timedelta(hours=3)
    rig.source.contests = [contest(starts=new_start)]
    rig.at(START - timedelta(hours=24) + timedelta(minutes=10))
    await rig.tick()

    notices = [(m["chat_id"], str(m["text"])) for m in rig.sent()]
    assert [chat for chat, body in notices if "rescheduled" in body] == [CHAT]
    assert f'unix="{int(new_start.timestamp())}"' in notices[0][1]
    async with rig.sessions() as session:
        due = (
            await session.execute(
                text("select due_at from reminders where chat_id = :c and offset_min = 60"),
                {"c": OTHER},
            )
        ).scalar_one()
    assert due == new_start - timedelta(hours=1)  # unsent reminders moved with the contest
    assert (await rig.reminders(CHAT))[1440] == "sent"  # the sent one stays sent


async def test_a_moved_contest_does_not_notify_chats_that_were_never_warned(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.source.contests = [contest(starts=START + timedelta(hours=1))]
    await rig.tick()
    assert not rig.sent()
    assert (await rig.reminders())[60] == "scheduled"


async def test_cancelling_tells_only_the_chats_that_were_warned(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    await rig.tick()
    rig.fake.calls.clear()
    rig.source.contests = [contest(phase=ContestPhase.CANCELLED)]
    await rig.tick()
    assert ["cancelled" in str(m["text"]) for m in rig.sent()] == [True]
    assert await rig.reminders() == {1440: "sent", 60: "cancelled", 10: "cancelled", -2: "sent"}


async def test_a_cancelled_contest_nobody_heard_about_is_withdrawn_silently(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.source.contests = [contest(phase=ContestPhase.CANCELLED)]
    await rig.tick()
    assert set((await rig.reminders()).values()) == {"cancelled"}
    assert not rig.sent()


async def test_a_contest_removed_from_the_list_counts_as_cancelled(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    await rig.tick()
    rig.fake.calls.clear()
    rig.source.contests = []
    await rig.tick()
    assert ["cancelled" in str(m["text"]) for m in rig.sent()] == [True]
    async with rig.sessions() as session:
        phase = (await session.execute(text("select phase from contests"))).scalar_one()
    assert phase == "CANCELLED"


async def test_a_contest_that_started_cancels_the_rest_silently(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.source.contests = [contest(phase=ContestPhase.CODING)]
    rig.at(START + timedelta(minutes=1))
    await rig.tick()
    assert set((await rig.reminders()).values()) == {"cancelled"}
    assert not rig.sent()


async def test_finished_contests_are_not_stored(rig: Rig) -> None:
    rig.source.contests = [contest(1, phase=ContestPhase.FINISHED), contest(2)]
    await rig.build().tick()
    async with rig.sessions() as session:
        ids = (await session.execute(text("select external_id from contests"))).scalars().all()
    assert list(ids) == [2]


async def test_concurrent_claims_never_overlap(rig: Rig) -> None:
    await rig.add_chat()
    async with rig.sessions() as session, session.begin():
        for i in range(10):
            await session.execute(
                text(
                    "insert into reminders (chat_id, platform, contest_id, offset_min, due_at, state)"
                    " values (:c, 'codeforces', :i, 10, :now, 'scheduled')"
                ),
                {"c": CHAT, "i": 1000 + i, "now": rig.now},
            )

    async def claim() -> list[int]:
        async with rig.sessions() as session, session.begin():
            got = await repos.claim_due_reminders(session, "codeforces", now=rig.now, limit=6)
            await asyncio.sleep(0.1)  # hold the locks while the other worker claims
            return [c.contest_id for c in got]

    first, second = await asyncio.gather(claim(), claim())
    assert not set(first) & set(second)
    assert len(first) + len(second) == 10


async def _force_due(rig: Rig) -> None:
    await rig.add_chat()
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    await rig.tick()  # plans and sends; callers clear the calls and set errors before the next tick


async def test_flood_control_puts_the_reminder_back_and_it_is_sent_later(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()  # plan while everything is ahead
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    rig.fake.send_error = TelegramRetryAfter(METHOD, "Too Many Requests", 5)
    assert await rig.tick() == 0
    assert (await rig.reminders())[1440] == "scheduled"
    rig.fake.send_error = None
    assert await rig.tick() == 1
    assert (await rig.reminders())[1440] == "sent"


async def test_network_failures_are_retried_a_limited_number_of_times(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    rig.fake.send_error = TelegramNetworkError(METHOD, "boom")
    for _ in range(rem.MAX_ATTEMPTS + 2):
        await rig.tick()
    assert rig.fake.send_attempts == rem.MAX_ATTEMPTS
    assert (await rig.reminders())[1440] == "sent"  # given up, never sent twice


async def test_a_chat_that_blocked_the_bot_is_marked_removed(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    rig.at(START - timedelta(hours=24) + timedelta(seconds=5))
    rig.fake.send_error = TelegramForbiddenError(METHOD, "Forbidden: bot was blocked")
    await rig.tick()
    async with rig.sessions() as session:
        chat = await repos.get_chat(session, CHAT)
    assert chat is not None
    assert chat.status == "removed"


async def test_switching_reminders_off_and_on(rig: Rig) -> None:
    await rig.add_chat()
    await rig.tick()
    async with rig.sessions() as session, session.begin():
        await repos.set_reminder_offsets(session, CHAT, ())
    assert set((await rig.reminders()).values()) == {"cancelled"}
    await rig.tick()
    assert set((await rig.reminders()).values()) == {"cancelled"}  # not resurrected while off
    async with rig.sessions() as session, session.begin():
        await repos.set_reminder_offsets(session, CHAT, (1440, 60, 10))
    await rig.tick()
    assert set((await rig.reminders()).values()) == {"scheduled"}


def test_tg_time_uses_the_reader_zone_for_the_fallback_text() -> None:
    html = str(rem.tg_time(START, "Asia/Tashkent"))
    assert f'unix="{int(START.timestamp())}"' in html
    assert "21.11 19:35" in html
    assert "21.11 14:35" in str(rem.tg_time(START, None))
    assert "21.11 14:35" in str(rem.tg_time(START, "Not/AZone"))


def test_reminder_text_variants() -> None:
    i18n = I18n()
    chat = repos.ChatRecord(1, "private", "en", "UTC", "playful", "active", (1440, 60, 10), True)
    row = repos.ContestRow(7, "A <b>&</b> B", "BEFORE", START, 7200)
    day, _ = rem.render_reminder(i18n, chat, row, 1440)
    assert "starts in 24 hours" in day
    assert "A &lt;b&gt;&amp;&lt;/b&gt; B" in day  # the name is escaped, the time markup is not
    assert "<tg-time" in day
    quarter, _ = rem.render_reminder(i18n, chat, row, 15)
    assert "starts in 15 minutes" in quarter
    neutral, _ = rem.render_reminder(i18n, replace(chat, tone="neutral"), row, 60)
    assert "⏰" not in neutral
    moved, markup = rem.render_reminder(i18n, chat, row, repos.NOTICE_MOVED)
    assert "rescheduled" in moved
    assert markup is not None
    cancelled, none_markup = rem.render_reminder(i18n, chat, row, repos.NOTICE_CANCELLED)
    assert "cancelled" in cancelled
    assert none_markup is None


def test_duration_text() -> None:
    assert rem.duration_text(7200) == "2:00"
    assert rem.duration_text(9000) == "2:30"
    assert rem.duration_text(None) == "-"


def test_reminder_text_for_three_days_and_two_hours() -> None:
    i18n = I18n()
    chat = repos.ChatRecord(1, "private", "en", "UTC", "playful", "active", (4320, 120), True)
    row = repos.ContestRow(7, "Round", "BEFORE", START, 7200)
    assert "starts in 3 days" in rem.render_reminder(i18n, chat, row, 4320)[0]
    assert "starts in 2 hours" in rem.render_reminder(i18n, chat, row, 120)[0]
    ru = replace(chat, language="ru")
    assert "через 3 дня" in rem.render_reminder(i18n, ru, row, 4320)[0]
