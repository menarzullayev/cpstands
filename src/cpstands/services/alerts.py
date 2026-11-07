"""Alert detection: compare a standings snapshot with the stored one and queue what is new.

Everything one poll produces - the new snapshots, the event facts and the per-chat outbox rows -
is written in a single transaction (transactional outbox, ADR-003), so a crash never loses an
event and a replayed poll never repeats one: facts and deliveries have deterministic keys.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.domain.contest import FullStandings, ProblemStatus, StandingRow, handle_key

PLATFORM = "codeforces"
BASELINE_WINDOW_S = 600  # a contest this young is news from its first problem on
BATCH_WINDOW_S = 15  # alerts of one poll wait this long so a chat gets one message
VARIANTS = 3  # playful wordings per alert kind

log = structlog.get_logger(__name__)

Kind = Literal["solve", "systest_fail", "systest_pass"]
_ACCEPTED = {ProblemStatus.ACCEPTED.value, ProblemStatus.PROVISIONAL.value}


@dataclass(frozen=True, slots=True)
class Detected:
    kind: Kind
    handle: str
    problem: str
    problem_name: str
    time_s: int | None
    event_key: str
    occurred_at: datetime

    @property
    def is_alert(self) -> bool:
        return self.kind != "systest_pass"  # a pass is recorded, not announced


def snapshot_of(row: StandingRow) -> repos.Snapshot:
    return [(r.status.value, r.rejected_attempts, r.time_s) for r in row.problems]


def variant_of(event_key: str) -> int:
    """A stable pick among the playful wordings, so a replayed alert reads the same."""
    return int(hashlib.sha1(event_key.encode()).hexdigest(), 16) % VARIANTS  # noqa: S324


def detect(
    previous: repos.Snapshot | None,
    row: StandingRow,
    handle: str,
    standings: FullStandings,
    *,
    now: datetime,
) -> list[Detected]:
    """The solves and system-test results that appeared between two snapshots of one row."""
    contest = standings.contest
    if previous is None:
        young = (
            contest.starts_at is None
            or (now - contest.starts_at).total_seconds() <= BASELINE_WINDOW_S
        )
        if not young:
            return []  # first sight of a handle in a running contest: take it as the baseline
        previous = [(ProblemStatus.NOT_TRIED.value, 0, None)] * len(row.problems)
    found: list[Detected] = []
    key = handle_key(handle)
    for index, result in enumerate(row.problems):
        old_status, _, old_time = (
            previous[index] if index < len(previous) else ("not_tried", 0, None)
        )
        new_status = result.status.value
        problem = standings.problems[index] if index < len(standings.problems) else None
        label = problem.index if problem else str(index)
        title = problem.name if problem else ""
        kind: Kind | None = None
        time_s = result.time_s
        if new_status in _ACCEPTED and old_status not in _ACCEPTED:
            kind = "solve"
        elif old_status == ProblemStatus.PROVISIONAL.value:
            if new_status == ProblemStatus.ACCEPTED.value:
                kind = "systest_pass"
            elif new_status not in _ACCEPTED:
                kind, time_s = "systest_fail", old_time
        elif old_status == ProblemStatus.ACCEPTED.value and new_status not in _ACCEPTED:
            kind, time_s = "systest_fail", old_time  # an accepted solution that was overturned
        if kind is None:
            continue
        occurred = (
            contest.starts_at + timedelta(seconds=time_s)
            if contest.starts_at is not None and time_s is not None
            else standings.fetched_at
        )
        found.append(
            Detected(
                kind=kind,
                handle=handle,
                problem=label,
                problem_name=title,
                time_s=time_s,
                event_key=f"{PLATFORM}|{contest.external_id}|{key}|{label}|{kind}|{time_s or 0}",
                occurred_at=occurred,
            )
        )
    return found


@dataclass(frozen=True, slots=True)
class ProcessResult:
    events: int
    queued: int


class AlertService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._now = now

    async def process(self, standings: FullStandings) -> ProcessResult:
        """Detect what changed for the followed handles and queue alerts, in one transaction."""
        now = self._now()
        contest_id = standings.contest.external_id
        events = 0
        queued = 0
        async with self._sessions() as session, session.begin():
            watched = await repos.watched_keys_of_active_chats(session, PLATFORM)
            matches = [
                (row, handle)
                for row in standings.rows
                for handle in row.handles
                if handle_key(handle) in watched
            ]
            if not matches:
                return ProcessResult(0, 0)
            keys = sorted({handle_key(handle) for _, handle in matches})
            previous = await repos.load_snapshots(session, PLATFORM, contest_id, keys)
            watchers = await repos.watchers_of(session, PLATFORM, keys)
            for row, handle in matches:
                key = handle_key(handle)
                for event in detect(previous.get(key), row, handle, standings, now=now):
                    fresh = await repos.insert_solve_event(
                        session,
                        event_key=event.event_key,
                        platform=PLATFORM,
                        contest_id=contest_id,
                        handle_key=key,
                        problem=event.problem,
                        kind=event.kind,
                        occurred_at=event.occurred_at,
                    )
                    if not fresh:
                        continue
                    events += 1
                    if not event.is_alert:
                        continue
                    payload = _payload(event, standings)
                    for chat_id in watchers.get(key, []):
                        if await repos.enqueue_alert(
                            session,
                            chat_id,
                            event.event_key,
                            payload,
                            not_before=now + timedelta(seconds=BATCH_WINDOW_S),
                        ):
                            queued += 1
                await repos.save_snapshot(
                    session,
                    PLATFORM,
                    contest_id,
                    key,
                    rank=row.rank,
                    points=row.points,
                    penalty=row.penalty,
                    official=row.participant_type == "CONTESTANT",
                    problems=snapshot_of(row),
                )
        if events:
            log.info("alerts_detected", contest_id=contest_id, events=events, queued=queued)
        return ProcessResult(events, queued)


def _payload(event: Detected, standings: FullStandings) -> dict[str, object]:
    return {
        "kind": event.kind,
        "handle": event.handle,
        "contest_id": standings.contest.external_id,
        "contest_name": standings.contest.name,
        "problem": event.problem,
        "problem_name": event.problem_name,
        "time_s": event.time_s,
        "v": variant_of(event.event_key),
        "at": event.occurred_at.isoformat(),
    }
