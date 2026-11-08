"""Test doubles for the contest source."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from cpstands.domain.contest import (
    Contest,
    ContestList,
    ContestPhase,
    ContestRatingChange,
    FetchMeta,
    FullStandings,
    HandleResolution,
    Problem,
    ProblemResult,
    ProblemStatus,
    RatingChange,
    RatingResult,
    StandingRow,
    UserRating,
    handle_key,
)
from cpstands.sources.base import PermanentSourceError, RetryableSourceError


class FakeSource:
    """Knows a fixed set of handles; spelling is canonicalized like user.info does."""

    platform = "codeforces"

    def __init__(
        self,
        existing: Sequence[str],
        *,
        fail: bool = False,
        standings: dict[int, FullStandings] | None = None,
        delay_s: float = 0.0,
        contests: list[Contest] | None = None,
        ratings: dict[str, UserRating] | None = None,
        histories: dict[str, list[RatingChange]] | None = None,
        contest_changes: dict[int, list[ContestRatingChange]] | None = None,
    ) -> None:
        self.histories = histories or {}
        self.contest_changes = contest_changes or {}
        self.ratings = ratings or {}
        self.rating_fetches = 0
        self.contests: list[Contest] = contests or []
        self.delay_s = delay_s
        self.standings = standings or {}
        self.full_fetches = 0
        self._existing = {handle_key(h): h for h in existing}
        self.fail = fail
        self.calls = 0

    async def resolve_handles(self, handles: Sequence[str]) -> HandleResolution:
        self.calls += 1
        if self.fail:
            raise RetryableSourceError("down")
        known = {
            handle_key(h): self._existing[handle_key(h)]
            for h in handles
            if handle_key(h) in self._existing
        }
        unknown = tuple(h for h in handles if handle_key(h) not in self._existing)
        return HandleResolution(known=known, unknown=unknown)

    async def fetch_ratings(self, handles: Sequence[str]) -> RatingResult:
        self.rating_fetches += 1
        if self.fail:
            raise RetryableSourceError("down")
        known = [self.ratings[handle_key(h)] for h in handles if handle_key(h) in self.ratings]
        unknown = tuple(h for h in handles if handle_key(h) not in self.ratings)
        return RatingResult(ratings=tuple(known), unknown=unknown)

    async def fetch_rating_history(self, handle: str) -> tuple[RatingChange, ...]:
        if self.fail:
            raise RetryableSourceError("down")
        return tuple(self.histories.get(handle_key(handle), ()))

    async def fetch_contest_rating_changes(
        self, contest_id: int
    ) -> tuple[ContestRatingChange, ...]:
        if self.fail:
            raise RetryableSourceError("down")
        if contest_id not in self.contest_changes:
            raise PermanentSourceError(f"contestId: Rating changes unavailable for {contest_id}")
        return tuple(self.contest_changes[contest_id])

    async def list_contests(self) -> ContestList:
        if self.fail:
            raise RetryableSourceError("down")
        now = datetime.now(UTC)
        meta = FetchMeta(now, 0.0, 0, 0, None, None)
        return ContestList(contests=tuple(self.contests), skipped=0, meta=meta)

    async def fetch_full_standings(self, contest_id: int) -> FullStandings:
        self.full_fetches += 1
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail:
            raise RetryableSourceError("down")
        if contest_id not in self.standings:
            raise PermanentSourceError(f"contestId: Contest with id {contest_id} not found")
        return self.standings[contest_id]


def make_standings(
    *,
    contest_id: int = 1970,
    rows: int = 60,
    problems: int = 21,
    kind: str = "ICPC",
    phase: ContestPhase = ContestPhase.FINISHED,
    name: str = "Test Contest",
) -> FullStandings:
    """A synthetic table: row i solved the first (problems - i % problems) problems."""
    contest = Contest(
        platform="codeforces",
        external_id=contest_id,
        name=name,
        phase=phase,
        kind=kind,
        starts_at=None,
        duration_s=18000,
    )
    table = []
    for i in range(rows):
        solved = problems - i % problems
        results = tuple(
            ProblemResult(ProblemStatus.ACCEPTED, i % 3, 600 + 60 * j, 500.0 * (j + 1))
            if j < solved
            else ProblemResult(
                ProblemStatus.REJECTED if j == solved else ProblemStatus.NOT_TRIED,
                2 if j == solved else 0,
                None,
                0.0,
            )
            for j in range(problems)
        )
        table.append(
            StandingRow(
                rank=i + 1,
                who=f"user{i}" if i % 2 else f"Team number {i} of the very long name",
                handles=(f"user{i}",),
                points=float(solved),
                penalty=1000 + i,
                participant_type="CONTESTANT",
                problems=results,
            )
        )
    return FullStandings(
        contest=contest,
        problems=tuple(Problem(f"P{k + 1}", f"Problem {k + 1}", None) for k in range(problems)),
        rows=tuple(table),
        fetched_at=datetime(2026, 11, 8, 12, 0, tzinfo=UTC),
    )
