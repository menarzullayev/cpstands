"""Post-contest summaries: how the followed handles finished and how their ratings moved."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from cpstands import platforms
from cpstands.domain.contest import (
    ContestRatingChange,
    FullStandings,
    ProblemStatus,
    StandingRow,
    handle_key,
)
from cpstands.services.standings import StandingsService
from cpstands.sources.base import PermanentSourceError, SourcePort

CHANGES_TTL_S = 1800.0
UNAVAILABLE_TTL_S = 120.0
MAX_CACHED = 16


@dataclass(frozen=True, slots=True)
class FriendResult:
    handle: str
    rank: int
    solved: int
    old_rating: int | None = None
    new_rating: int | None = None

    @property
    def delta(self) -> int | None:
        if self.old_rating is None or self.new_rating is None:
            return None
        return self.new_rating - self.old_rating


@dataclass(frozen=True, slots=True)
class Summary:
    contest_id: int
    name: str
    participants: int
    rated: bool
    results: tuple[FriendResult, ...]
    platform: str = platforms.CODEFORCES

    def payload(self) -> dict[str, object]:
        return {
            "kind": "summary",
            "platform": self.platform,
            "contest_id": self.contest_id,
            "contest_name": self.name,
            "participants": self.participants,
            "rated": self.rated,
            "results": [
                {
                    "handle": r.handle,
                    "rank": r.rank,
                    "solved": r.solved,
                    "old": r.old_rating,
                    "new": r.new_rating,
                }
                for r in self.results
            ],
        }


def _solved(row: StandingRow) -> int:
    return sum(1 for p in row.problems if p.status is ProblemStatus.ACCEPTED)


def build_summary(
    standings: FullStandings,
    friends: Mapping[str, str],
    changes: Mapping[str, ContestRatingChange] | None,
) -> Summary:
    """The finish of every followed handle that took part officially, best rank first."""
    official = [row for row in standings.rows if row.participant_type == "CONTESTANT"]
    best: dict[str, FriendResult] = {}
    for row in official:
        for handle in row.handles:
            key = handle_key(handle)
            if key not in friends:
                continue
            change = changes.get(key) if changes else None
            result = FriendResult(
                handle=friends[key],
                rank=row.rank,
                solved=_solved(row),
                old_rating=change.old_rating if change else None,
                new_rating=change.new_rating if change else None,
            )
            if key not in best or result.rank < best[key].rank:
                best[key] = result
    results = tuple(sorted(best.values(), key=lambda r: (r.rank, handle_key(r.handle))))
    return Summary(
        contest_id=standings.contest.external_id,
        name=standings.contest.name,
        participants=len(official),
        rated=changes is not None,
        results=results,
    )


class SummaryService:
    def __init__(
        self,
        source: SourcePort,
        standings: StandingsService,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source = source
        self._standings = standings
        self._clock = clock
        self._changes: dict[int, tuple[dict[str, ContestRatingChange] | None, float]] = {}

    @property
    def platform(self) -> str:
        return self._source.platform

    async def rating_changes(self, contest_id: int) -> dict[str, ContestRatingChange] | None:
        """Rating changes by handle key, or ``None`` while Codeforces has not published any."""
        now = self._clock()
        cached = self._changes.get(contest_id)
        if cached is not None:
            ttl = CHANGES_TTL_S if cached[0] is not None else UNAVAILABLE_TTL_S
            if now - cached[1] < ttl:
                return cached[0]
        try:
            fetched = await self._source.fetch_contest_rating_changes(contest_id)
        except PermanentSourceError:
            found = None  # an unrated contest, or the changes are not out yet
        else:
            found = {handle_key(c.handle): c for c in fetched} or None
        if len(self._changes) >= MAX_CACHED:
            self._changes.clear()
        self._changes[contest_id] = (found, now)
        return found

    async def summary(
        self, contest_id: int, friends: Mapping[str, str], *, with_ratings: bool = True
    ) -> Summary:
        standings = await self._standings.get_shared(contest_id, max_age_s=600.0)
        changes = await self.rating_changes(contest_id) if with_ratings else None
        return replace(build_summary(standings, friends, changes), platform=self.platform)
