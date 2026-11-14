"""Upsolve alerts: detection, the outbox, the watcher's schedule and delivery."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import alerts as bot_alerts
from cpstands.bot import upsolve as bot_upsolve
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import Submission
from cpstands.i18n import I18n
from cpstands.services import upsolve as svc
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource
from tests.support.telegram import FakeSession, make_bot

START = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
ENDED = START + timedelta(hours=2)
CID = 2290
CHAT = -1001
NOW = ENDED + timedelta(hours=5)
CONTEST = repos.ContestRow(CID, "Round <1>", "FINISHED", START, 7200)
CONTESTS = {CID: CONTEST}


def sub(
    index: str = "C",
    *,
    verdict: str | None = "OK",
    kind: str = "PRACTICE",
    at: datetime = NOW - timedelta(minutes=5),
    cid: int = CID,
    sid: int = 1,
) -> Submission:
    return Submission(sid, cid, index, f"Problem {index}", verdict, kind, at)


# ------------------------------------------------------------------ detection (no database)


def test_a_fresh_practice_solve_after_the_contest_is_an_upsolve() -> None:
    found = svc.detect_upsolves("Tourist", [sub("C")], CONTESTS, now=NOW)
    assert [(u.handle, u.contest_id, u.problem, u.problem_name) for u in found] == [
        ("Tourist", CID, "C", "Problem C")
    ]
    assert found[0].event_key == f"codeforces|{CID}|tourist|C|upsolve|0"
    assert found[0].payload()["kind"] == "upsolve"


def test_a_problem_solved_during_the_contest_is_not_an_upsolve() -> None:
    during = sub("C", kind="CONTESTANT", at=START + timedelta(minutes=40), sid=1)
    again = sub("C", sid=2)  # solved again in practice
    assert svc.detect_upsolves("x", [during, again], CONTESTS, now=NOW) == []
    out_of_competition = sub("C", kind="OUT_OF_COMPETITION", at=START + timedelta(minutes=40))
    assert svc.detect_upsolves("x", [out_of_competition, again], CONTESTS, now=NOW) == []


@pytest.mark.parametrize(
    "bad",
    [
        sub("C", verdict="WRONG_ANSWER"),
        sub("C", verdict=None),
        sub("C", kind="VIRTUAL"),
        sub("C", kind="CONTESTANT"),
        sub("C", at=ENDED - timedelta(minutes=1)),  # before the contest was over
        sub("C", cid=999),  # not a contest we know about
        sub("C", at=NOW - timedelta(hours=3)),  # old news
    ],
)
def test_submissions_that_are_not_fresh_practice_solves_are_ignored(bad: Submission) -> None:
    assert svc.detect_upsolves("x", [bad], CONTESTS, now=NOW) == []


def test_only_the_first_accepted_practice_submission_counts() -> None:
    first = sub("C", at=NOW - timedelta(hours=2), sid=1)  # old: the news has already passed
    second = sub("C", at=NOW - timedelta(minutes=5), sid=2)
    assert svc.detect_upsolves("x", [first, second], CONTESTS, now=NOW) == []
    fresh_first = sub("C", at=NOW - timedelta(minutes=20), sid=1)
    found = svc.detect_upsolves("x", [second, fresh_first], CONTESTS, now=NOW)
    assert [u.at for u in found] == [fresh_first.created_at]


def test_several_problems_come_out_in_order() -> None:
    a = sub("B", at=NOW - timedelta(minutes=30), sid=1)
    b = sub("A", at=NOW - timedelta(minutes=10), sid=2)
    assert [u.problem for u in svc.detect_upsolves("x", [b, a], CONTESTS, now=NOW)] == ["B", "A"]


# ------------------------------------------------------------------ database


@dataclass
class Rig:
    sessions: async_sessionmaker[AsyncSession]
    fake: FakeSession
    clock: FakeClock
    source: FakeSource
    now: datetime

    def watcher(self) -> bot_upsolve.UpsolveWatcher:
        return bot_upsolve.UpsolveWatcher(
            self.sessions,
            self.source,  # type: ignore[arg-type]
            svc.UpsolveService(self.sessions, now=lambda: self.now),
            clock=self.clock.monotonic,
            now=lambda: self.now,
            sleep=self.clock.sleep,
        )

    def notifier(self) -> bot_alerts.AlertNotifier:
        return bot_alerts.AlertNotifier(
            make_bot(self.fake),
            self.sessions,
            I18n(),
            clock=self.clock.monotonic,
            now=lambda: self.now + timedelta(minutes=1),
            sleep=self.clock.sleep,
        )

    async def chat(
        self,
        chat_id: int,
        *handles: str,
        upsolve: bool = True,
        alerts: bool = True,
        added: datetime = START - timedelta(days=1),
        tone: str = "playful",
    ) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_chat(session, chat_id, "supergroup")
            await repos.set_language(session, chat_id, "en")
            await repos.set_tone(session, chat_id, tone)
            await repos.set_alerts_enabled(session, chat_id, alerts)
            await repos.set_status(session, chat_id, "active")
            for handle in handles:
                await session.execute(
                    text(
                        "insert into watched_handles (chat_id, platform, handle_key, handle_display,"
                        " notify_upsolve, added_at) values (:c, 'codeforces', :k, :d, :u, :a)"
                    ),
                    {"c": chat_id, "k": handle.lower(), "d": handle, "u": upsolve, "a": added},
                )

    async def contest(self, cid: int = CID, *, start: datetime = START) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_contest(
                session, "codeforces", cid, "Round <1>", "FINISHED", start, 7200
            )

    async def count(self, query: str) -> int:
        async with self.sessions() as session:
            return int((await session.execute(text(query))).scalar_one())


@pytest.fixture
async def rig(migrated_database: str) -> AsyncIterator[Rig]:
    engine = create_engine(migrated_database, pool_size=4)
    source = FakeSource(["tourist", "petr"], submissions={"tourist": [sub("C")]})
    yield Rig(create_session_factory(engine), FakeSession(), FakeClock(), source, NOW)
    await engine.dispose()


async def test_an_upsolve_is_queued_and_delivered_once(rig: Rig) -> None:
    await rig.chat(CHAT, "Tourist")
    await rig.contest()
    watcher = rig.watcher()
    assert await watcher.tick() == 1
    assert await rig.count("select count(*) from solve_events where kind = 'upsolve'") == 1
    assert await rig.notifier().tick() == 1
    body = str(rig.fake.sent()[-1]["text"])
    assert "Tourist" in body
    assert "Problem C" in body
    assert "Round &lt;1&gt;" in body
    # the same submission seen again, even by a restarted watcher, is not news
    rig.clock.advance(bot_upsolve.PER_HANDLE_S + 1)
    assert await watcher.tick() == 0
    assert await rig.watcher().tick() == 0
    assert await rig.count("select count(*) from deliveries") == 1


async def test_only_chats_that_followed_at_the_time_and_want_it_are_told(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.chat(-1002, "tourist", upsolve=False)
    await rig.chat(-1003, "tourist", alerts=False)
    await rig.chat(-1004, "tourist", added=NOW)  # started following after the solve
    await rig.contest()
    assert await rig.watcher().tick() == 1
    assert await rig.count("select count(*) from deliveries where chat_id = -1001") == 1
    assert await rig.count("select count(*) from deliveries where chat_id <> -1001") == 0


async def test_no_recent_contest_means_no_requests(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    assert await rig.watcher().tick() == 0  # no contest at all
    await rig.contest(start=START - timedelta(days=5))
    assert await rig.watcher().tick() == 0  # the window of 72 hours has passed
    assert rig.source.status_fetches == []


async def test_nobody_wanting_upsolves_means_no_requests(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", upsolve=False)
    await rig.contest()
    assert await rig.watcher().tick() == 0
    assert rig.source.status_fetches == []


async def test_handles_are_polled_in_small_batches_and_then_every_ten_minutes(rig: Rig) -> None:
    names = [f"h{i}" for i in range(12)]
    rig.source = FakeSource(names)
    await rig.chat(CHAT, *names)
    await rig.contest()
    watcher = rig.watcher()
    await watcher.tick()
    assert len(rig.source.status_fetches) == bot_upsolve.MAX_PER_TICK
    await watcher.tick()
    await watcher.tick()
    assert sorted(rig.source.status_fetches) == sorted(names)  # everyone once, nobody twice
    await watcher.tick()
    assert len(rig.source.status_fetches) == 12  # nothing is due yet
    rig.clock.advance(bot_upsolve.PER_HANDLE_S + 1)
    await watcher.tick()
    assert len(rig.source.status_fetches) == 12 + bot_upsolve.MAX_PER_TICK


async def test_a_failing_source_backs_off_and_an_unknown_handle_is_left_alone(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", "ghost")  # ghost is not a Codeforces user
    await rig.contest()
    watcher = rig.watcher()
    rig.source.fail = True
    assert await watcher.tick() == 0
    first = len(rig.source.status_fetches)
    assert await watcher.tick() == 0
    assert len(rig.source.status_fetches) == first  # backing off
    rig.source.fail = False
    rig.clock.advance(bot_upsolve.RETRY_S + 1)
    assert await watcher.tick() == 1  # tourist recovers
    rig.clock.advance(bot_upsolve.PER_HANDLE_S + 1)
    await watcher.tick()
    assert rig.source.status_fetches.count("ghost") == 2  # tried again after the retry, then parked


async def test_the_neutral_tone_has_its_own_wording(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", tone="neutral")
    await rig.contest()
    await rig.watcher().tick()
    await rig.notifier().tick()
    assert "after the contest" in str(rig.fake.sent()[-1]["text"])
