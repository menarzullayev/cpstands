"""Operator view of the running system: source health, pause switches, queues and counters."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import metrics
from cpstands.domain.contest import (
    ContestList,
    ContestRatingChange,
    FullStandings,
    HandleResolution,
    RatingChange,
    RatingResult,
    StandingsFetch,
)
from cpstands.sources.base import (
    PermanentSourceError,
    RetryableSourceError,
    SourceError,
    SourcePort,
)

SEND_WINDOW_S = 300.0


class SourcePausedError(RetryableSourceError):
    """The operator paused this source; callers treat it like any other outage."""

    def __init__(self, name: str) -> None:
        super().__init__(f"source {name} is paused by the operator")


@dataclass(slots=True)
class SourceHealth:
    last_success: datetime | None = None
    consecutive_errors: int = 0
    paused: bool = False


class OpsState:
    """In-memory operational state; the pause flag is also persisted (``source_health``)."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._clock = clock
        self._now = now
        self.started = clock()
        self.sources: dict[str, SourceHealth] = {}
        self._sends: deque[tuple[float, bool]] = deque()
        self._beats: dict[str, float] = {}
        self.open_alerts: dict[str, datetime] = {}

    def source(self, name: str) -> SourceHealth:
        return self.sources.setdefault(name, SourceHealth())

    def record_source(self, name: str, *, ok: bool) -> None:
        health = self.source(name)
        if ok:
            health.consecutive_errors = 0
            health.last_success = self._now()
        else:
            health.consecutive_errors += 1
            metrics.SOURCE_ERRORS.inc(source=name)

    def is_paused(self, name: str) -> bool:
        return self.source(name).paused

    def record_send(self, *, ok: bool) -> None:
        self._sends.append((self._clock(), ok))
        self._trim()

    def send_failure_rate(self) -> tuple[float, int]:
        """Failure share and sample count of sends in the last five minutes."""
        self._trim()
        total = len(self._sends)
        failed = sum(1 for _, ok in self._sends if not ok)
        return (failed / total if total else 0.0), total

    def _trim(self) -> None:
        cutoff = self._clock() - SEND_WINDOW_S
        while self._sends and self._sends[0][0] < cutoff:
            self._sends.popleft()

    def beat(self, name: str) -> None:
        self._beats[name] = self._clock()

    def seconds_since_beat(self, name: str) -> float | None:
        moment = self._beats.get(name)
        return None if moment is None else self._clock() - moment

    def uptime_s(self) -> float:
        return self._clock() - self.started


class ObservedSource:
    """Wraps a ``SourcePort``: honours the pause switch and records health and metrics."""

    def __init__(self, inner: SourcePort, ops: OpsState) -> None:
        self._inner = inner
        self._ops = ops
        self.platform = inner.platform

    async def _call[T](self, method: str, call: Callable[[], Awaitable[T]]) -> T:
        if self._ops.is_paused(self.platform):
            metrics.SOURCE_REQUESTS.inc(method=method, outcome="paused")
            raise SourcePausedError(self.platform)
        started = time.monotonic()
        try:
            result = await call()
        except PermanentSourceError:
            metrics.SOURCE_REQUESTS.inc(method=method, outcome="rejected")
            raise
        except SourceError:
            self._ops.record_source(self.platform, ok=False)
            metrics.SOURCE_REQUESTS.inc(method=method, outcome="error")
            raise
        metrics.SOURCE_SECONDS.observe(time.monotonic() - started, method=method)
        metrics.SOURCE_REQUESTS.inc(method=method, outcome="ok")
        self._ops.record_source(self.platform, ok=True)
        return result

    async def list_contests(self) -> ContestList:
        return await self._call("list_contests", self._inner.list_contests)

    async def fetch_standings(self, contest_id: int, watched: frozenset[str]) -> StandingsFetch:
        return await self._call(
            "fetch_standings", lambda: self._inner.fetch_standings(contest_id, watched)
        )

    async def fetch_full_standings(self, contest_id: int) -> FullStandings:
        return await self._call(
            "fetch_full_standings", lambda: self._inner.fetch_full_standings(contest_id)
        )

    async def fetch_rating_history(self, handle: str) -> tuple[RatingChange, ...]:
        return await self._call(
            "fetch_rating_history", lambda: self._inner.fetch_rating_history(handle)
        )

    async def fetch_contest_rating_changes(
        self, contest_id: int
    ) -> tuple[ContestRatingChange, ...]:
        return await self._call(
            "fetch_contest_rating_changes",
            lambda: self._inner.fetch_contest_rating_changes(contest_id),
        )

    async def fetch_ratings(self, handles: Sequence[str]) -> RatingResult:
        return await self._call("fetch_ratings", lambda: self._inner.fetch_ratings(handles))

    async def resolve_handles(self, handles: object) -> HandleResolution:
        return await self._call(
            "resolve_handles",
            lambda: self._inner.resolve_handles(handles),  # type: ignore[arg-type]
        )


# --- persistence of the pause flag ------------------------------------------------------


async def save_source_state(
    sessions: async_sessionmaker[AsyncSession], name: str, health: SourceHealth
) -> None:
    async with sessions() as session, session.begin():
        await session.execute(
            text(
                """
                INSERT INTO source_health (source, last_success_at, consecutive_errors, paused)
                VALUES (:s, :ok, :errors, :paused)
                ON CONFLICT (source) DO UPDATE
                  SET last_success_at = EXCLUDED.last_success_at,
                      consecutive_errors = EXCLUDED.consecutive_errors,
                      paused = EXCLUDED.paused
                """
            ),
            {
                "s": name,
                "ok": health.last_success,
                "errors": health.consecutive_errors,
                "paused": health.paused,
            },
        )


async def load_source_state(sessions: async_sessionmaker[AsyncSession], ops: OpsState) -> None:
    async with sessions() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT source, last_success_at, consecutive_errors, paused FROM source_health"
                )
            )
        ).all()
    for source, last_success, errors, paused in rows:
        ops.sources[str(source)] = SourceHealth(last_success, int(errors), bool(paused))


# --- numbers for /status, /stats and /metrics -------------------------------------------


@dataclass(frozen=True, slots=True)
class Snapshot:
    chats: dict[str, int]
    pending_alerts: int
    scheduled_reminders: int
    overdue_reminders: int
    live_messages: int
    watched_contests: int
    handles: int


async def snapshot(session: AsyncSession, *, now: datetime) -> Snapshot:
    async def scalar(sql: str, **params: object) -> int:
        return int((await session.execute(text(sql), params)).scalar_one())

    chats = {
        str(status): int(count)
        for status, count in (
            await session.execute(text("SELECT status, count(*) FROM chats GROUP BY status"))
        ).all()
    }
    return Snapshot(
        chats=chats,
        pending_alerts=await scalar(
            "SELECT count(*) FROM deliveries WHERE kind = 'alert' AND state = 'pending'"
        ),
        scheduled_reminders=await scalar(
            "SELECT count(*) FROM reminders WHERE state = 'scheduled'"
        ),
        overdue_reminders=await scalar(
            "SELECT count(*) FROM reminders WHERE state = 'scheduled' "
            "AND due_at < CAST(:cut AS timestamptz) AND due_at > CAST(:old AS timestamptz)",
            cut=now - timedelta(seconds=60),
            old=now - timedelta(minutes=30),
        ),
        live_messages=await scalar(
            "SELECT count(*) FROM standings_messages WHERE state = 'active'"
        ),
        watched_contests=await scalar(
            "SELECT count(*) FROM contests "
            "WHERE phase IN ('CODING','PENDING_SYSTEM_TEST','SYSTEM_TEST')"
        ),
        handles=await scalar("SELECT count(DISTINCT handle_key) FROM watched_handles"),
    )


@dataclass(frozen=True, slots=True)
class Stats:
    chats_by_type: dict[str, int]
    handles_total: int
    events_24h: int
    reminders_sent_24h: int
    alerts_pending: int
    alerts_failed_24h: int


async def stats(session: AsyncSession, *, now: datetime) -> Stats:
    day = now - timedelta(hours=24)

    async def scalar(sql: str, **params: object) -> int:
        return int((await session.execute(text(sql), params)).scalar_one())

    by_type = {
        str(kind): int(count)
        for kind, count in (
            await session.execute(
                text("SELECT chat_type, count(*) FROM chats WHERE status = 'active' GROUP BY 1")
            )
        ).all()
    }
    return Stats(
        chats_by_type=by_type,
        handles_total=await scalar("SELECT count(*) FROM watched_handles"),
        events_24h=await scalar(
            "SELECT count(*) FROM solve_events WHERE created_at > CAST(:d AS timestamptz)", d=day
        ),
        reminders_sent_24h=await scalar(
            "SELECT count(*) FROM reminders WHERE state = 'sent' AND offset_min > 0 "
            "AND sent_at > CAST(:d AS timestamptz)",
            d=day,
        ),
        alerts_pending=await scalar(
            "SELECT count(*) FROM deliveries WHERE kind = 'alert' AND state = 'pending'"
        ),
        alerts_failed_24h=await scalar(
            "SELECT count(*) FROM deliveries WHERE kind = 'alert' AND state = 'failed' "
            "AND not_before > CAST(:d AS timestamptz)",
            d=day,
        ),
    )


async def refresh_gauges(
    session: AsyncSession, ops: OpsState, *, now: datetime, ages: dict[int, float]
) -> None:
    """Fill the scrape-time gauges from the database and the in-memory state."""
    metrics.UPTIME.set(ops.uptime_s())
    shot = await snapshot(session, now=now)
    metrics.CHATS.clear()
    for status, count in shot.chats.items():
        metrics.CHATS.set(count, status=status)
    metrics.QUEUE_DEPTH.set(shot.pending_alerts, queue="alerts")
    metrics.QUEUE_DEPTH.set(shot.overdue_reminders, queue="reminders_overdue")
    metrics.QUEUE_DEPTH.set(shot.scheduled_reminders, queue="reminders_scheduled")
    metrics.STANDINGS_AGE.clear()
    for contest_id, age in ages.items():
        metrics.STANDINGS_AGE.set(age, contest=str(contest_id))
    for name, health in ops.sources.items():
        metrics.SOURCE_STREAK.set(health.consecutive_errors, source=name)
        metrics.SOURCE_PAUSED.set(1 if health.paused else 0, source=name)
