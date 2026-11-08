"""Operator side: pause, health, deletion on request, retention, readiness, operator alerts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import metrics
from cpstands.bot.monitor import (
    REPEAT_S,
    SEND_SAMPLE_MIN,
    SOURCE_ERROR_STREAK,
    STALE_AFTER_S,
    OperatorAlerts,
)
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.http_server import ReadinessChecker, build_app
from cpstands.i18n import I18n
from cpstands.services import ops
from cpstands.services.privacy import delete_chat_data
from cpstands.services.retention import RetentionService
from cpstands.services.standings import StandingsService
from cpstands.sources.base import PermanentSourceError, RetryableSourceError
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource, make_standings
from tests.support.telegram import FakeSession, make_bot

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
OWNER = 555


@pytest.fixture
async def sessions(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(migrated_database, pool_size=3)
    yield create_session_factory(engine)
    await engine.dispose()


async def scalar(sessions: async_sessionmaker[AsyncSession], sql: str) -> int:
    async with sessions() as session:
        return int((await session.execute(text(sql))).scalar_one())


# ------------------------------------------------------------------------- OpsState / source


def test_send_failures_are_counted_in_a_five_minute_window() -> None:
    clock = FakeClock()
    state = ops.OpsState(clock=clock.monotonic)
    for _ in range(9):
        state.record_send(ok=True)
    state.record_send(ok=False)
    rate, total = state.send_failure_rate()
    assert (round(rate, 2), total) == (0.1, 10)
    clock.advance(ops.SEND_WINDOW_S + 1)
    assert state.send_failure_rate() == (0.0, 0)


def test_source_streak_resets_on_success_and_beats_are_timed() -> None:
    clock = FakeClock()
    state = ops.OpsState(clock=clock.monotonic, now=lambda: NOW)
    state.record_source("codeforces", ok=False)
    state.record_source("codeforces", ok=False)
    assert state.source("codeforces").consecutive_errors == 2
    state.record_source("codeforces", ok=True)
    assert state.source("codeforces").consecutive_errors == 0
    assert state.source("codeforces").last_success == NOW
    assert state.seconds_since_beat("scheduler") is None
    state.beat("scheduler")
    clock.advance(7)
    assert state.seconds_since_beat("scheduler") == 7


async def test_a_paused_source_is_not_called_and_reads_as_an_outage() -> None:
    state = ops.OpsState()
    inner = FakeSource([], standings={1: make_standings(contest_id=1)})
    source = ops.ObservedSource(inner, state)  # type: ignore[arg-type]
    await source.fetch_full_standings(1)
    state.source("codeforces").paused = True
    with pytest.raises(ops.SourcePausedError):
        await source.fetch_full_standings(1)
    with pytest.raises(RetryableSourceError):  # the same class callers already handle
        await source.list_contests()
    assert inner.full_fetches == 1
    state.source("codeforces").paused = False
    await source.fetch_full_standings(1)
    assert inner.full_fetches == 2


async def test_source_errors_count_toward_the_streak_but_rejections_do_not() -> None:
    state = ops.OpsState()
    inner = FakeSource([], standings={1: make_standings(contest_id=1)})
    source = ops.ObservedSource(inner, state)  # type: ignore[arg-type]
    with pytest.raises(PermanentSourceError):
        await source.fetch_full_standings(404)  # a missing contest is not an outage
    assert state.source("codeforces").consecutive_errors == 0
    inner.fail = True
    before = metrics.SOURCE_ERRORS.value(source="codeforces")
    for _ in range(3):
        with pytest.raises(RetryableSourceError):
            await source.fetch_full_standings(1)
    assert state.source("codeforces").consecutive_errors == 3
    assert metrics.SOURCE_ERRORS.value(source="codeforces") == before + 3
    inner.fail = False
    await source.fetch_full_standings(1)
    assert state.source("codeforces").consecutive_errors == 0


async def test_the_pause_flag_survives_a_restart(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    state = ops.OpsState()
    state.source("codeforces").paused = True
    await ops.save_source_state(sessions, "codeforces", state.source("codeforces"))
    fresh = ops.OpsState()
    await ops.load_source_state(sessions, fresh)
    assert fresh.is_paused("codeforces")
    state.source("codeforces").paused = False
    await ops.save_source_state(sessions, "codeforces", state.source("codeforces"))
    await ops.load_source_state(sessions, fresh)
    assert not fresh.is_paused("codeforces")


# ----------------------------------------------------------------------- deletion on request


async def _seed_chat(sessions: async_sessionmaker[AsyncSession], chat_id: int) -> None:
    async with sessions() as session, session.begin():
        await repos.upsert_chat(session, chat_id, "supergroup")
        await repos.set_status(session, chat_id, "active")
        await session.execute(
            text(
                "insert into watched_handles (chat_id, platform, handle_key, handle_display) "
                "values (:c, 'codeforces', 'tourist', 'tourist'), (:c, 'codeforces', 'petr', 'Petr')"
            ),
            {"c": chat_id},
        )
        await session.execute(
            text(
                "insert into reminders (chat_id, platform, contest_id, offset_min, due_at) "
                "values (:c, 'codeforces', 1, 60, now())"
            ),
            {"c": chat_id},
        )
        await session.execute(
            text(
                "insert into deliveries (chat_id, kind, event_key, payload) "
                "values (:c, 'alert', 'k', '{}')"
            ),
            {"c": chat_id},
        )
        await session.execute(
            text(
                "insert into standings_messages (chat_id, platform, contest_id, message_id) "
                "values (:c, 'codeforces', 1, 9)"
            ),
            {"c": chat_id},
        )


async def test_deleting_a_chat_removes_everything_keyed_by_it(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_chat(sessions, -1)
    await _seed_chat(sessions, -2)
    result = await delete_chat_data(sessions, -1, now=NOW)
    assert result is not None
    assert (result.handles, result.reminders, result.alerts, result.live_messages) == (2, 1, 1, 1)
    for table in ("chats", "watched_handles", "reminders", "deliveries", "standings_messages"):
        assert await scalar(sessions, f"select count(*) from {table} where chat_id = -1") == 0
    assert await scalar(sessions, "select count(*) from watched_handles where chat_id = -2") == 2
    assert (
        await scalar(
            sessions,
            "select count(*) from deletion_requests where subject_id = -1 and completed_at is not null",
        )
        == 1
    )


async def test_deleting_twice_or_an_unknown_chat_is_harmless(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_chat(sessions, -1)
    assert await delete_chat_data(sessions, -1) is not None
    assert await delete_chat_data(sessions, -1) is None
    assert await delete_chat_data(sessions, -99) is None
    assert await scalar(sessions, "select count(*) from deletion_requests") == 1


# -------------------------------------------------------------------------------- retention


async def _seed_old_and_new(sessions: async_sessionmaker[AsyncSession]) -> None:
    old, new = NOW - timedelta(days=45), NOW - timedelta(days=2)
    async with sessions() as session, session.begin():
        for chat_id, status, when in (
            (-1, "removed", old),
            (-2, "removed", new),
            (-3, "active", old),
        ):
            await repos.upsert_chat(session, chat_id, "supergroup")
            await session.execute(
                text("update chats set status = :s, updated_at = :t where chat_id = :c"),
                {"s": status, "t": when, "c": chat_id},
            )
        for cid, when in ((1, old), (2, new)):
            await session.execute(
                text(
                    "insert into contests (platform, external_id, name, phase, updated_at) "
                    "values ('codeforces', :i, 'C', 'FINISHED', :t)"
                ),
                {"i": cid, "t": when},
            )
            await session.execute(
                text(
                    "insert into participant_results "
                    "(platform, contest_id, handle_key, problem_results, official, updated_at) "
                    "values ('codeforces', :i, 'h', '[]', true, :t)"
                ),
                {"i": cid, "t": when},
            )
            await session.execute(
                text(
                    "insert into solve_events (event_key, platform, contest_id, handle_key, problem, "
                    "kind, occurred_at, created_at) values (:k, 'codeforces', :i, 'h', 'A', 'solve', :t, :t)"
                ),
                {"k": f"k{cid}", "i": cid, "t": when},
            )
        for state, when in (("sent", old), ("sent", new), ("pending", old)):
            await session.execute(
                text(
                    "insert into deliveries (chat_id, kind, event_key, payload, state, not_before) "
                    "values (-3, 'alert', :k, '{}', :s, :t)"
                ),
                {"k": f"{state}{when}", "s": state, "t": when},
            )
        for offset, state, when in ((60, "sent", old), (10, "sent", new), (1440, "scheduled", old)):
            await session.execute(
                text(
                    "insert into reminders (chat_id, platform, contest_id, offset_min, due_at, state) "
                    "values (-3, 'codeforces', 1, :o, :t, :s)"
                ),
                {"o": offset, "s": state, "t": when},
            )


async def test_retention_removes_only_what_is_older_than_the_window(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_old_and_new(sessions)
    removed = await RetentionService(sessions, now=lambda: NOW).run()
    assert removed["participant_results"] == 1
    assert removed["solve_events"] == 1
    assert removed["contests"] == 1
    assert removed["deliveries"] == 1  # the old sent one; the old pending one must stay
    assert removed["reminders"] == 1  # the old sent one; the old scheduled one must stay
    assert removed["removed_chats"] == 1
    assert await scalar(sessions, "select count(*) from chats") == 2
    assert await scalar(sessions, "select count(*) from deliveries where state = 'pending'") == 1
    assert await scalar(sessions, "select count(*) from reminders where state = 'scheduled'") == 1
    assert await scalar(sessions, "select count(*) from contests where external_id = 2") == 1


async def test_retention_runs_once_a_day_even_across_restarts(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    clock = {"now": NOW}
    service = RetentionService(sessions, now=lambda: clock["now"])
    assert await service.run_if_due() is not None
    assert (
        await RetentionService(sessions, now=lambda: clock["now"]).run_if_due() is None
    )  # restart
    clock["now"] = NOW + timedelta(hours=23)
    assert await service.run_if_due() is None
    clock["now"] = NOW + timedelta(hours=25)
    assert await service.run_if_due() is not None


# ------------------------------------------------------------------- readiness and http


def _head() -> str:
    from alembic.script import ScriptDirectory

    from cpstands.__main__ import alembic_config

    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert head is not None
    return head


async def test_readiness_follows_database_migrations_and_scheduler(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock()
    state = ops.OpsState(clock=clock.monotonic)
    ready = ReadinessChecker(sessions, state, _head(), clock=clock.monotonic)
    first = await ready.check()
    assert first.ready  # still inside the start-up grace period
    assert first.checks["scheduler"] == "starting"

    clock.advance(100)
    assert not (await ready.check()).ready  # cached for ten seconds
    clock.advance(11)
    stalled = await ready.check()
    assert not stalled.ready
    assert stalled.checks["scheduler"] == "stalled"

    state.beat("scheduler")
    clock.advance(11)
    assert (await ready.check()).ready
    wrong = ReadinessChecker(sessions, state, "9999", clock=clock.monotonic)
    result = await wrong.check()
    assert not result.ready
    assert result.checks["migrations"].startswith("at ")


async def test_a_broken_database_is_not_ready() -> None:
    engine = create_engine("postgresql+asyncpg://nobody:x@127.0.0.1:1/none", pool_size=1)
    state = ops.OpsState()
    state.beat("scheduler")
    result = await ReadinessChecker(create_session_factory(engine), state, None).check()
    await engine.dispose()
    assert not result.ready
    assert result.checks["database"].startswith("error")


async def test_the_three_endpoints(sessions: async_sessionmaker[AsyncSession]) -> None:
    state = ops.OpsState()
    state.beat("scheduler")
    refreshed: list[bool] = []

    async def refresh() -> None:
        refreshed.append(True)
        metrics.UPTIME.set(12.5)

    app = build_app(ReadinessChecker(sessions, state, None, commit="abc123"), refresh)
    async with TestClient(TestServer(app)) as client:
        health = await client.get("/healthz")
        assert (health.status, (await health.text()).strip()) == (200, "ok")
        ready = await client.get("/readyz")
        assert ready.status == 200
        payload = await ready.json()
        assert payload["ready"] is True
        assert payload["commit"] == "abc123"  # which build answered
        scraped = await client.get("/metrics")
        body = await scraped.text()
        assert scraped.status == 200
        assert scraped.headers["Content-Type"].startswith("text/plain")
        assert "cpstands_process_uptime_seconds 12.5" in body
        assert refreshed == [True]


# -------------------------------------------------------------------------- operator alerts


@dataclass
class MonitorRig:
    monitor: OperatorAlerts
    state: ops.OpsState
    fake: FakeSession
    standings: StandingsService
    clock: FakeClock
    sessions: async_sessionmaker[AsyncSession]
    when: list[datetime]

    def texts(self) -> list[str]:
        return [str(m["text"]) for m in self.fake.sent()]

    def advance(self, seconds: float) -> None:
        self.clock.advance(seconds)
        self.when[0] += timedelta(seconds=seconds)


@pytest.fixture
async def monitor_rig(sessions: async_sessionmaker[AsyncSession]) -> MonitorRig:
    clock = FakeClock()
    when = [NOW]
    state = ops.OpsState(clock=clock.monotonic, now=lambda: when[0])
    fake = FakeSession()
    source = FakeSource([], standings={7: make_standings(contest_id=7)})
    standings = StandingsService(source, clock=clock.monotonic)  # type: ignore[arg-type]
    monitor = OperatorAlerts(
        make_bot(fake), sessions, state, standings, I18n(), OWNER,
        clock=clock.monotonic, now=lambda: when[0], sleep=clock.sleep,
    )  # fmt: skip
    return MonitorRig(monitor, state, fake, standings, clock, sessions, when)


async def test_three_source_errors_alert_the_owner_once_then_resolve(
    monitor_rig: MonitorRig,
) -> None:
    rig = monitor_rig
    for _ in range(SOURCE_ERROR_STREAK - 1):
        rig.state.record_source("codeforces", ok=False)
    assert await rig.monitor.tick() == 0  # two in a row is not yet a problem
    rig.state.record_source("codeforces", ok=False)
    assert await rig.monitor.tick() == 1
    assert "codeforces" in rig.texts()[0]
    assert await rig.monitor.tick() == 0  # deduplicated while it stays open
    rig.advance(REPEAT_S - 60)
    assert await rig.monitor.tick() == 0
    rig.advance(120)
    assert await rig.monitor.tick() == 1  # reminded after half an hour
    rig.state.record_source("codeforces", ok=True)
    assert await rig.monitor.tick() == 1
    assert "source:codeforces" in rig.texts()[-1]  # the all-clear names the rule
    assert await rig.monitor.tick() == 0
    assert not rig.state.open_alerts


async def test_pausing_a_source_silences_its_outage_alerts(monitor_rig: MonitorRig) -> None:
    for _ in range(5):
        monitor_rig.state.record_source("codeforces", ok=False)
    monitor_rig.state.source("codeforces").paused = True
    assert await monitor_rig.monitor.tick() == 0


async def test_old_standings_of_a_running_contest_alert(monitor_rig: MonitorRig) -> None:
    rig = monitor_rig
    async with rig.sessions() as session, session.begin():
        await repos.upsert_contest(session, "codeforces", 7, "C", "CODING", NOW, 7200)
        await repos.upsert_chat(session, -1, "supergroup")
        await repos.set_status(session, -1, "active")
        await session.execute(
            text(
                "insert into watched_handles (chat_id, platform, handle_key, handle_display) "
                "values (-1, 'codeforces', 'x', 'x')"
            )
        )
    await rig.standings.refresh(7)
    assert await rig.monitor.tick() == 0  # fresh data
    rig.advance(STALE_AFTER_S + 1)
    assert await rig.monitor.tick() == 1
    assert "7" in rig.texts()[0]
    await rig.standings.refresh(7)
    assert await rig.monitor.tick() == 1  # fresh again: the all-clear
    assert "stale" in rig.texts()[-1]


async def test_a_reminder_more_than_a_minute_late_alerts(monitor_rig: MonitorRig) -> None:
    rig = monitor_rig
    async with rig.sessions() as session, session.begin():
        await repos.upsert_chat(session, -1, "supergroup")
        await session.execute(
            text(
                "insert into reminders (chat_id, platform, contest_id, offset_min, due_at) "
                "values (-1, 'codeforces', 1, 60, :t)"
            ),
            {"t": NOW - timedelta(seconds=90)},
        )
    assert await rig.monitor.tick() == 1
    assert "1 ta eslatma" in rig.texts()[0]


async def test_a_high_send_failure_rate_alerts_only_with_enough_samples(
    monitor_rig: MonitorRig,
) -> None:
    rig = monitor_rig
    for _ in range(SEND_SAMPLE_MIN - 1):
        rig.state.record_send(ok=False)
    assert await rig.monitor.tick() == 0  # too few samples to judge
    rig.state.record_send(ok=False)
    assert await rig.monitor.tick() == 1
    assert "100%" in rig.texts()[0]


async def test_an_undelivered_operator_alert_is_retried_not_forgotten(
    monitor_rig: MonitorRig,
) -> None:
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendMessage

    rig = monitor_rig
    for _ in range(3):
        rig.state.record_source("codeforces", ok=False)
    rig.fake.send_error = TelegramNetworkError(SendMessage(chat_id=1, text="x"), "boom")
    assert await rig.monitor.tick() == 0
    assert not rig.state.open_alerts
    rig.fake.send_error = None
    assert await rig.monitor.tick() == 1


async def test_without_an_owner_nothing_is_sent(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    state = ops.OpsState()
    for _ in range(5):
        state.record_source("codeforces", ok=False)
    fake = FakeSession()
    monitor = OperatorAlerts(
        make_bot(fake), sessions, state,
        StandingsService(FakeSource([])), I18n(), None,  # type: ignore[arg-type]
    )  # fmt: skip
    assert await monitor.tick() == 0
    assert not fake.sent()
