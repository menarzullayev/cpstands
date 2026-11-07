"""Full-standings access with a short cache, so paging through a table costs one fetch."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable

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
    def __init__(self, source: SourcePort, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._source = source
        self._clock = clock
        self._cache: OrderedDict[int, tuple[FullStandings, float, float]] = OrderedDict()
        self._locks: dict[int, asyncio.Lock] = {}

    async def get(self, contest_id: int, *, refresh: bool = False) -> FullStandings:
        """Return the standings; one fetch serves every concurrent caller."""
        if len(self._locks) > MAX_LOCKS:
            self._locks = {k: v for k, v in self._locks.items() if v.locked() or k in self._cache}
        lock = self._locks.setdefault(contest_id, asyncio.Lock())
        async with lock:
            cached = self._cache.get(contest_id)
            now = self._clock()
            if cached is not None:
                standings, fetched, expires = cached
                fresh_enough = now - fetched < MIN_REFRESH_AGE_S
                if now < expires and (not refresh or fresh_enough):
                    self._cache.move_to_end(contest_id)
                    return standings
            standings = await self._source.fetch_full_standings(contest_id)
            ttl = ACTIVE_TTL_S if standings.contest.phase.is_active else FINISHED_TTL_S
            self._cache[contest_id] = (standings, now, now + ttl)
            self._cache.move_to_end(contest_id)
            while len(self._cache) > MAX_CACHED_CONTESTS:
                evicted, _ = self._cache.popitem(last=False)
                self._locks.pop(evicted, None)
            return standings
