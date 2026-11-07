"""Full-standings access with a short cache, so paging through a table costs one fetch."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime

from cpstands.domain.contest import FullStandings
from cpstands.sources.base import SourcePort

# Codeforces itself caches standings for a minute, so a fresher copy cannot exist.
ACTIVE_TTL_S = 60.0
FINISHED_TTL_S = 600.0
# A manual refresh may skip the cache only when the copy is at least this old.
MIN_REFRESH_AGE_S = 15.0
MAX_CACHED_CONTESTS = 8
MAX_LOCKS = 256


class StandingsService:
    def __init__(
        self,
        source: SourcePort,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._source = source
        self._clock = clock
        self._now = now
        self._cache: OrderedDict[int, tuple[FullStandings, float, float]] = OrderedDict()
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, contest_id: int) -> asyncio.Lock:
        if len(self._locks) > MAX_LOCKS:
            self._locks = {k: v for k, v in self._locks.items() if v.locked() or k in self._cache}
        return self._locks.setdefault(contest_id, asyncio.Lock())

    async def get(self, contest_id: int, *, refresh: bool = False) -> FullStandings:
        """Return the standings; one fetch serves every concurrent caller."""
        async with self._lock(contest_id):
            cached = self._cache.get(contest_id)
            now = self._clock()
            if cached is not None:
                standings, fetched, expires = cached
                fresh_enough = now - fetched < MIN_REFRESH_AGE_S
                if now < expires and (not refresh or fresh_enough):
                    self._cache.move_to_end(contest_id)
                    return standings
            return await self._fetch_and_store(contest_id, now)

    async def get_shared(self, contest_id: int, *, max_age_s: float) -> FullStandings:
        """A copy at most ``max_age_s`` old, so two consumers on one contest share one fetch."""
        async with self._lock(contest_id):
            now = self._clock()
            cached = self._cache.get(contest_id)
            if cached is not None and now - cached[1] <= max_age_s:
                return cached[0]
            return await self._fetch_and_store(contest_id, now)

    def age_s(self, contest_id: int) -> float | None:
        """Seconds since the newest copy of this contest was fetched, if there is one."""
        cached = self._cache.get(contest_id)
        return None if cached is None else self._clock() - cached[1]

    async def refresh(self, contest_id: int) -> FullStandings:
        """Always fetch; the live updater schedules its own fetches."""
        async with self._lock(contest_id):
            return await self._fetch_and_store(contest_id, self._clock())

    async def _fetch_and_store(self, contest_id: int, now: float) -> FullStandings:
        standings = await self._source.fetch_full_standings(contest_id)
        if standings.contest.phase.is_active:
            ttl = ACTIVE_TTL_S
            if standings.expires_at is not None:
                left = (standings.expires_at - self._now()).total_seconds() + 1.0
                ttl = min(max(left, 1.0), ACTIVE_TTL_S)
        else:
            ttl = FINISHED_TTL_S
        self._cache[contest_id] = (standings, now, now + ttl)
        self._cache.move_to_end(contest_id)
        while len(self._cache) > MAX_CACHED_CONTESTS:
            evicted, _ = self._cache.popitem(last=False)
            self._locks.pop(evicted, None)
        return standings
