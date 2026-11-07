"""Alerts: detection, transactional outbox, batching, delivery and watching (real PostgreSQL)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import SendMessage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import alerts as bot_alerts
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import (
    Contest,
    ContestPhase,
    FullStandings,
    Problem,
    ProblemResult,
    ProblemStatus,
    StandingRow,
)
from cpstands.i18n import I18n
from cpstands.services import alerts as svc
from cpstands.services.standings import StandingsService
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource
from tests.support.telegram import FakeSession, make_bot

START = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
METHOD = SendMessage(chat_id=1, text="x")
A, R, P, N = "accepted", "rejected", "provisional", "not_tried"
CHAT, OTHER = -1001, -1002

type Cell = tuple[str, int, int | None]


def table(
    rows: dict[str, Sequence[Cell]],
    *,
    cid: int = 2290,
    phase: ContestPhase = ContestPhase.CODING,
    fetched: datetime = START + timedelta(minutes=5),
    teams: dict[str, tuple[str, ...]] | None = None,
) -> FullStandings:
    width = max(len(cells) for cells in rows.values())
    contest = Contest("codeforces", cid, "Round <1> & co", phase, "CF", START, 7200)
    standing = []
    for rank, (who, cells) in enumerate(rows.items(), 1):
        problems = tuple(
            ProblemResult(
                ProblemStatus(status), rejected, time_s, 100.0 if status in {A, P} else 0.0
            )
            for status, rejected, time_s in cells
        )
        members = (teams or {}).get(who, (who,))
        standing.append(StandingRow(rank, who, members, 0.0, 0, "CONTESTANT", problems))
    problem_list = tuple(Problem(chr(65 + i), f"Problem <{i}>", None) for i in range(width))
    return FullStandings(contest, problem_list, tuple(standing), fetched)


def cells(*statuses: str, base: int = 600) -> list[Cell]:
    return [(s, 0, base + 60 * i if s in {A, P} else None) for i, s in enumerate(statuses)]


# ------------------------------------------------------------------ detection (no database)


def test_a_new_accept_is_a_solve_with_a_deterministic_key() -> None:
    before = table({"tourist": cells(N, N)})
    after = table({"tourist": cells(A, N)})
    snapshot = svc.snapshot_of(before.rows[0])
    events = svc.detect(snapshot, after.rows[0], "tourist", after, now=START + timedelta(hours=1))
    assert [(e.kind, e.problem) for e in events] == [("solve", "A")]
    assert events[0].event_key == "codeforces|2290|tourist|A|solve|600"
    assert events[0].occurred_at == START + timedelta(seconds=600)
    assert (
        svc.detect(snapshot, after.rows[0], "tourist", after, now=START)[0].event_key
        == events[0].event_key
    )


def test_nothing_changed_nothing_detected() -> None:
    same = table({"tourist": cells(A, R)})
    snapshot = svc.snapshot_of(same.rows[0])
    assert svc.detect(snapshot, same.rows[0], "tourist", same, now=START + timedelta(hours=1)) == []


def test_a_provisional_solve_that_fails_the_system_tests_is_announced() -> None:
    before = table({"x": cells(P, N)}, phase=ContestPhase.SYSTEM_TEST)
    failed = table({"x": [(R, 1, None), (N, 0, None)]}, phase=ContestPhase.SYSTEM_TEST)
    snapshot = svc.snapshot_of(before.rows[0])
    events = svc.detect(snapshot, failed.rows[0], "x", failed, now=START + timedelta(hours=3))
    assert [(e.kind, e.problem, e.time_s, e.is_alert) for e in events] == [
        ("systest_fail", "A", 600, True)
    ]


def test_a_provisional_solve_that_passes_is_recorded_but_not_announced() -> None:
    before = table({"x": cells(P)}, phase=ContestPhase.SYSTEM_TEST)
    passed = table({"x": [(A, 0, 600)]})
    events = svc.detect(svc.snapshot_of(before.rows[0]), passed.rows[0], "x", passed, now=START)
    assert [(e.kind, e.is_alert) for e in events] == [("systest_pass", False)]


def test_an_overturned_accept_counts_as_a_failure() -> None:
    before = table({"x": cells(A)})
    after = table({"x": [(N, 0, None)]})
    events = svc.detect(svc.snapshot_of(before.rows[0]), after.rows[0], "x", after, now=START)
    assert [e.kind for e in events] == ["systest_fail"]


def test_first_sight_of_a_handle_in_a_running_contest_is_only_a_baseline() -> None:
    standings = table({"tourist": cells(A, A, A)})
    late = START + timedelta(hours=1)
    assert svc.detect(None, standings.rows[0], "tourist", standings, now=late) == []
    early = START + timedelta(minutes=5)
    assert len(svc.detect(None, standings.rows[0], "tourist", standings, now=early)) == 3


def test_variants_are_stable_and_in_range() -> None:
    keys = [f"codeforces|1|h|{i}|solve|0" for i in range(60)]
    picks = [svc.variant_of(k) for k in keys]
    assert picks == [svc.variant_of(k) for k in keys]
    assert set(picks) == set(range(svc.VARIANTS))


# ---------------------------------------------------------------------- outbox (database)


@dataclass
class Rig:
    sessions: async_sessionmaker[AsyncSession]
    fake: FakeSession
    clock: FakeClock
    now: datetime

    def service(self) -> svc.AlertService:
        return svc.AlertService(self.sessions, now=lambda: self.now)

    def notifier(self) -> bot_alerts.AlertNotifier:
        return bot_alerts.AlertNotifier(
            make_bot(self.fake),
            self.sessions,
            I18n(),
            clock=self.clock.monotonic,
            now=lambda: self.now,
            sleep=self.clock.sleep,
        )

    async def chat(
        self,
        chat_id: int,
        *handles: str,
        active: bool = True,
        alerts: bool = True,
        tone: str = "playful",
    ) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_chat(session, chat_id, "supergroup")
            await repos.set_language(session, chat_id, "en")
            await repos.set_tone(session, chat_id, tone)
            await repos.set_alerts_enabled(session, chat_id, alerts)
            if active:
                await repos.set_status(session, chat_id, "active")
            for handle in handles:
                await session.execute(
                    text(
                        "insert into watched_handles (chat_id, platform, handle_key, handle_display)"
                        " values (:c, 'codeforces', :k, :d)"
                    ),
                    {"c": chat_id, "k": handle.lower(), "d": handle},
                )

    async def count(self, query: str) -> int:
        async with self.sessions() as session:
            return int((await session.execute(text(query))).scalar_one())

    def sent(self) -> list[dict[str, object]]:
        return self.fake.sent()

    async def wait_window(self) -> None:
        self.now += timedelta(seconds=svc.BATCH_WINDOW_S + 1)


@pytest.fixture
async def rig(migrated_database: str) -> AsyncIterator[Rig]:
    engine = create_engine(migrated_database, pool_size=4)
    yield Rig(
        create_session_factory(engine), FakeSession(), FakeClock(), START + timedelta(minutes=5)
    )
    await engine.dispose()


async def test_solves_are_queued_once_per_following_chat(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.chat(OTHER, "Tourist", "petr")
    await rig.chat(-1003, "someone")  # follows nobody in this table
    await rig.chat(-1004, "tourist", alerts=False)
    await rig.chat(-1005, "tourist", active=False)
    standings = table({"tourist": cells(A, N), "petr": cells(N, A)})
    result = await rig.service().process(standings)
    assert (result.events, result.queued) == (2, 3)  # tourist: 2 chats, petr: 1 chat
    assert await rig.count("select count(*) from solve_events") == 2
    assert await rig.count("select count(*) from deliveries where chat_id = -1001") == 1
    assert (
        await rig.count("select count(*) from deliveries where chat_id in (-1003,-1004,-1005)") == 0
    )
    assert await rig.count("select count(*) from participant_results") == 2


async def test_processing_the_same_poll_again_changes_nothing(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    standings = table({"tourist": cells(A, A)})
    service = rig.service()
    await service.process(standings)
    again = await service.process(standings)
    assert (again.events, again.queued) == (0, 0)
    assert await rig.count("select count(*) from deliveries") == 2


async def test_a_lost_snapshot_cannot_make_an_event_repeat(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    standings = table({"tourist": cells(A)})
    await rig.service().process(standings)
    async with rig.sessions() as session, session.begin():  # simulate a crash that lost snapshots
        await session.execute(text("delete from participant_results"))
    await rig.service().process(standings)
    assert await rig.count("select count(*) from solve_events") == 1
    assert await rig.count("select count(*) from deliveries") == 1


async def test_a_handle_added_mid_contest_gets_a_baseline_then_real_news(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    rig.now = START + timedelta(hours=1)
    await rig.service().process(table({"tourist": cells(A, A, N)}, fetched=rig.now))
    assert await rig.count("select count(*) from deliveries") == 0  # old news stays quiet
    await rig.service().process(table({"tourist": cells(A, A, A)}, fetched=rig.now))
    assert await rig.count("select count(*) from deliveries") == 1  # the new solve is announced


async def test_a_member_of_a_team_is_followed_through_the_team_row(rig: Rig) -> None:
    await rig.chat(CHAT, "ormlis")
    standings = table({"thinking": cells(A)}, teams={"thinking": ("Ormlis", "Mangooste")})
    result = await rig.service().process(standings)
    assert result.queued == 1
    payload = await rig.count("select count(*) from deliveries where payload->>'handle' = 'Ormlis'")
    assert payload == 1


async def test_system_test_failure_flow(rig: Rig) -> None:
    await rig.chat(CHAT, "x")
    service = rig.service()
    await service.process(table({"x": cells(P)}))
    assert await rig.count("select count(*) from deliveries where payload->>'kind' = 'solve'") == 1
    failed = table({"x": [(R, 1, None)]}, phase=ContestPhase.SYSTEM_TEST)
    await service.process(failed)
    assert (
        await rig.count("select count(*) from deliveries where payload->>'kind' = 'systest_fail'")
        == 1
    )


async def test_a_pass_is_stored_as_a_fact_but_not_queued(rig: Rig) -> None:
    await rig.chat(CHAT, "x")
    service = rig.service()
    await service.process(table({"x": cells(P)}))
    await service.process(table({"x": [(A, 0, 600)]}))
    assert await rig.count("select count(*) from solve_events where kind = 'systest_pass'") == 1
    assert await rig.count("select count(*) from deliveries") == 1


async def test_switching_alerts_off_withdraws_what_is_still_queued(rig: Rig) -> None:
    await rig.chat(CHAT, "x")
    await rig.service().process(table({"x": cells(A)}))
    async with rig.sessions() as session, session.begin():
        await repos.set_alerts_enabled(session, CHAT, False)
    await rig.wait_window()
    assert await rig.notifier().tick() == 0
    assert await rig.count("select count(*) from deliveries where state = 'failed'") == 1
    assert not rig.sent()


# --------------------------------------------------------------------- delivery (database)


async def test_alerts_of_one_chat_leave_as_one_message_after_the_batching_window(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", "petr")
    await rig.service().process(table({"tourist": cells(A, A), "petr": cells(A, N)}))
    assert await rig.notifier().tick() == 0  # the window is still open
    await rig.wait_window()
    assert await rig.notifier().tick() == 1
    message = str(rig.sent()[-1]["text"])
    assert message.count("\n") == 3  # a contest header and three solves
    assert message.startswith(("🏆", "<tg-emoji")) or "Round" in message
    assert "Round &lt;1&gt; &amp; co" in message  # the contest name is escaped
    assert '<a href="https://codeforces.com/profile/tourist">tourist</a>' in message
    assert '<a href="https://codeforces.com/contest/2290/problem/A">A</a>' in message
    assert "Problem &lt;0&gt;" in message
    assert await rig.notifier().tick() == 0  # nothing is sent twice


async def test_a_long_burst_is_split_into_several_messages(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.service().process(table({"tourist": cells(*([A] * 30))}))
    await rig.wait_window()
    sent = await rig.notifier().tick()
    assert sent == 3
    assert all(str(m["text"]).count("\n") <= bot_alerts.MAX_LINES_PER_MESSAGE for m in rig.sent())
    assert all(
        "Round &lt;1&gt;" in str(m["text"]) for m in rig.sent()
    )  # every part repeats the header
    assert sum(str(m["text"]).count("\n") for m in rig.sent()) == 30
    assert sum(rig.clock.sleeps) >= 2 * bot_alerts.MIN_GAP_S - 0.001  # spaced per chat


async def test_the_neutral_tone_and_playful_variants(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", tone="neutral")
    await rig.chat(OTHER, "tourist", tone="playful")
    await rig.service().process(table({"tourist": cells(A)}))
    await rig.wait_window()
    await rig.notifier().tick()
    by_chat = {int(m["chat_id"]): str(m["text"]) for m in rig.sent()}  # type: ignore[call-overload]
    assert "solved" in by_chat[CHAT]
    assert not any(ch in by_chat[CHAT] for ch in "🔥⚡🎯")
    assert any(ch in by_chat[OTHER] for ch in "🔥⚡🎯")


async def test_flood_control_puts_alerts_back_for_later(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.service().process(table({"tourist": cells(A)}))
    await rig.wait_window()
    rig.fake.send_error = TelegramRetryAfter(METHOD, "Too Many Requests", 30)
    assert await rig.notifier().tick() == 0
    assert await rig.count("select count(*) from deliveries where state = 'pending'") == 1
    rig.fake.send_error = None
    assert await rig.notifier().tick() == 0  # not before the pause
    rig.now += timedelta(seconds=40)
    assert await rig.notifier().tick() == 1


async def test_network_failures_are_retried_a_limited_number_of_times(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.service().process(table({"tourist": cells(A)}))
    await rig.wait_window()
    rig.fake.send_error = TelegramNetworkError(METHOD, "boom")
    for _ in range(bot_alerts.MAX_ATTEMPTS + 2):
        await rig.notifier().tick()
        rig.now += timedelta(seconds=60)
    assert rig.fake.send_attempts == bot_alerts.MAX_ATTEMPTS
    assert await rig.count("select count(*) from deliveries where state = 'failed'") == 1


async def test_a_chat_that_blocked_the_bot_is_removed_and_its_alerts_dropped(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.service().process(table({"tourist": cells(A)}))
    await rig.wait_window()
    rig.fake.send_error = TelegramForbiddenError(METHOD, "Forbidden: bot was blocked")
    await rig.notifier().tick()
    async with rig.sessions() as session:
        chat = await repos.get_chat(session, CHAT)
    assert chat is not None
    assert chat.status == "removed"
    assert await rig.count("select count(*) from deliveries where state = 'failed'") == 1


async def test_concurrent_claims_never_overlap(rig: Rig) -> None:
    import asyncio

    await rig.chat(CHAT, "tourist")
    await rig.service().process(table({"tourist": cells(*([A] * 10))}))
    await rig.wait_window()

    async def claim() -> list[int]:
        async with rig.sessions() as session, session.begin():
            got = await repos.claim_due_alerts(session, now=rig.now, limit=6)
            await asyncio.sleep(0.1)
            return [a.id for a in got]

    first, second = await asyncio.gather(claim(), claim())
    assert not set(first) & set(second)
    assert len(first) + len(second) == 10


# ----------------------------------------------------------------------- watcher (database)


async def test_the_watcher_polls_running_contests_with_followers_only(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    async with rig.sessions() as session, session.begin():
        for cid, phase in ((2290, "CODING"), (2291, "CODING"), (2292, "BEFORE")):
            await repos.upsert_contest(session, "codeforces", cid, f"C{cid}", phase, START, 7200)
    source = FakeSource(
        [],
        standings={2290: table({"tourist": cells(A)}), 2291: table({"nobody": cells(N)}, cid=2291)},
    )
    standings = StandingsService(source, clock=rig.clock.monotonic)  # type: ignore[arg-type]
    watcher = bot_alerts.AlertWatcher(
        rig.sessions, standings, rig.service(), clock=rig.clock.monotonic, now=lambda: rig.now
    )
    await watcher.tick()
    assert source.full_fetches == 2  # both running contests; the one in the future is left alone
    assert await rig.count("select count(*) from deliveries") == 1


async def test_the_watcher_follows_the_schedule_and_stops_after_the_final_poll(rig: Rig) -> None:
    await rig.chat(CHAT, "x")
    async with rig.sessions() as session, session.begin():
        await repos.upsert_contest(session, "codeforces", 2290, "C", "CODING", START, 7200)
    source = FakeSource([], standings={2290: table({"x": cells(P)})})
    standings = StandingsService(source, clock=rig.clock.monotonic)  # type: ignore[arg-type]
    watcher = bot_alerts.AlertWatcher(
        rig.sessions, standings, rig.service(), clock=rig.clock.monotonic, now=lambda: rig.now
    )
    await watcher.tick()
    await watcher.tick()
    assert source.full_fetches == 1  # not due yet

    rig.clock.advance(61)
    rig.now += timedelta(seconds=61)
    source.standings[2290] = table({"x": [(R, 1, None)]}, phase=ContestPhase.FINISHED)
    await watcher.tick()
    assert (
        await rig.count("select count(*) from deliveries where payload->>'kind' = 'systest_fail'")
        == 1
    )
    assert await rig.count("select count(*) from contests where phase = 'FINISHED'") == 1

    fetches = source.full_fetches
    rig.clock.advance(600)
    await watcher.tick()
    assert source.full_fetches == fetches  # a finished contest is not polled again


async def test_the_watcher_backs_off_when_the_source_is_down(rig: Rig) -> None:
    await rig.chat(CHAT, "x")
    async with rig.sessions() as session, session.begin():
        await repos.upsert_contest(session, "codeforces", 2290, "C", "CODING", START, 7200)
    source = FakeSource([], standings={2290: table({"x": cells(A)})}, fail=True)
    standings = StandingsService(source, clock=rig.clock.monotonic)  # type: ignore[arg-type]
    watcher = bot_alerts.AlertWatcher(
        rig.sessions, standings, rig.service(), clock=rig.clock.monotonic, now=lambda: rig.now
    )
    await watcher.tick()
    await watcher.tick()
    assert source.full_fetches == 1
    source.fail = False
    rig.clock.advance(bot_alerts.ERROR_BACKOFF_S + 1)
    await watcher.tick()
    assert await rig.count("select count(*) from deliveries") == 1


async def test_live_standings_and_alerts_share_one_fetch() -> None:
    clock = FakeClock()
    source = FakeSource([], standings={2290: table({"x": cells(A)})})
    standings = StandingsService(source, clock=clock.monotonic)  # type: ignore[arg-type]
    await standings.get_shared(2290, max_age_s=20)
    clock.advance(10)
    await standings.get_shared(2290, max_age_s=20)
    assert source.full_fetches == 1
    clock.advance(11)
    await standings.get_shared(2290, max_age_s=20)
    assert source.full_fetches == 2
