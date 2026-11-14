"""Upsolve alerts: a followed handle solved, after the contest, a problem it had not solved in it.

Codeforces no longer shows unofficial rows in the standings, so the only anonymous source is the
handle's own submission list (``user.status``). A submission counts when it is the first accepted
practice submission of that problem, was made after the contest ended, is fresh, and the same
problem was not already accepted during the contest. Facts and outbox rows are written in one
transaction with deterministic keys, so a replayed poll never repeats an alert.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import platforms
from cpstands.db import repos
from cpstands.domain.contest import Submission, handle_key
from cpstands.services.alerts import BATCH_WINDOW_S, variant_of

PLATFORM = platforms.CODEFORCES
WINDOW = timedelta(hours=72)  # contests that ended longer ago are not watched for upsolving
FRESH = timedelta(minutes=90)  # an older solve is history, not news
IN_CONTEST = {"CONTESTANT", "OUT_OF_COMPETITION"}

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Upsolve:
    handle: str
    contest_id: int
    contest_name: str
    problem: str
    problem_name: str
    at: datetime
    platform: str = PLATFORM

    @property
    def event_key(self) -> str:
        return (
            f"{self.platform}|{self.contest_id}|{handle_key(self.handle)}|{self.problem}|upsolve|0"
        )

    def payload(self) -> dict[str, object]:
        return {
            "kind": "upsolve",
            "platform": self.platform,
            "handle": self.handle,
            "contest_id": self.contest_id,
            "contest_name": self.contest_name,
            "problem": self.problem,
            "problem_name": self.problem_name,
            "time_s": None,
            "v": variant_of(self.event_key),
            "at": self.at.isoformat(),
        }


def contest_end(contest: repos.ContestRow) -> datetime | None:
    if contest.starts_at is None or contest.duration_s is None:
        return None
    return contest.starts_at + timedelta(seconds=contest.duration_s)


def detect_upsolves(
    handle: str,
    submissions: Sequence[Submission],
    contests: Mapping[int, repos.ContestRow],
    *,
    now: datetime,
    platform: str = PLATFORM,
) -> list[Upsolve]:
    """The fresh first practice solves of problems that were not solved during the contest."""
    solved_in_contest = {
        (s.contest_id, s.problem_index)
        for s in submissions
        if s.accepted and s.participant_type in IN_CONTEST
    }
    first: dict[tuple[int, str], Submission] = {}
    for sub in sorted(submissions, key=lambda s: s.created_at):
        if not sub.accepted or sub.participant_type != "PRACTICE":
            continue
        contest = contests.get(sub.contest_id)
        ended = contest_end(contest) if contest else None
        if contest is None or ended is None or sub.created_at <= ended:
            continue
        first.setdefault((sub.contest_id, sub.problem_index), sub)
    found: list[Upsolve] = []
    for (contest_id, index), sub in first.items():
        if (contest_id, index) in solved_in_contest or now - sub.created_at > FRESH:
            continue
        found.append(
            Upsolve(
                handle=handle,
                contest_id=contest_id,
                contest_name=contests[contest_id].name,
                problem=index,
                problem_name=sub.problem_name,
                at=sub.created_at,
                platform=platform,
            )
        )
    return sorted(found, key=lambda u: (u.at, u.problem))


class UpsolveService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        platform: str = PLATFORM,
    ) -> None:
        self._sessions = sessions
        self._now = now
        self._platform = platform

    @property
    def platform(self) -> str:
        return self._platform

    async def process(
        self,
        handle: str,
        submissions: Sequence[Submission],
        contests: Mapping[int, repos.ContestRow],
    ) -> int:
        """Record what is new and queue it for the chats that follow ``handle``; returns queued."""
        now = self._now()
        found = detect_upsolves(handle, submissions, contests, now=now, platform=self._platform)
        if not found:
            return 0
        key = handle_key(handle)
        queued = 0
        async with self._sessions() as session, session.begin():
            for upsolve in found:
                fresh = await repos.insert_solve_event(
                    session,
                    event_key=upsolve.event_key,
                    platform=self._platform,
                    contest_id=upsolve.contest_id,
                    handle_key=key,
                    problem=upsolve.problem,
                    kind="upsolve",
                    occurred_at=upsolve.at,
                )
                if not fresh:
                    continue
                for chat_id in await repos.upsolve_watchers(
                    session, self._platform, key, upsolve.at
                ):
                    if await repos.enqueue_alert(
                        session,
                        chat_id,
                        upsolve.event_key,
                        upsolve.payload(),
                        not_before=now + timedelta(seconds=BATCH_WINDOW_S),
                    ):
                        queued += 1
        if queued:
            log.info("upsolves_queued", handle=key, queued=queued)
        return queued
