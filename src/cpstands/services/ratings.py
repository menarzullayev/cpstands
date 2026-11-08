"""Friends' ratings with a short per-handle cache: one ``user.info`` call serves a whole list."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from cpstands.domain.contest import RatingChange, UserRating, handle_key
from cpstands.sources.base import SourcePort

TTL_S = 600.0
MIN_REFRESH_AGE_S = 30.0
MAX_CACHED = 5000


@dataclass(frozen=True, slots=True)
class RatingTable:
    """Ratings of a chat's handles, best first; ``unknown`` are handles Codeforces rejects."""

    rows: tuple[UserRating, ...]
    unknown: tuple[str, ...]
    fetched_at: datetime


def sort_key(rating: UserRating) -> tuple[int, int, str]:
    # Rated users by rating (high first), unrated ones after them, ties by handle.
    return (0 if rating.rating is not None else 1, -(rating.rating or 0), handle_key(rating.handle))


@dataclass(frozen=True, slots=True)
class RatingCard:
    """What ``/rating <handle>`` shows."""

    user: UserRating
    contests: int
    last: RatingChange | None


class RatingService:
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
        # key -> (rating or None when unknown to the platform, fetched at, canonical handle)
        self._cache: dict[str, tuple[UserRating | None, float, str]] = {}
        self._lock = asyncio.Lock()
        self._cards: dict[str, tuple[RatingCard | None, float]] = {}
        self._fetched_at = self._now()

    async def get(self, handles: Sequence[str], *, refresh: bool = False) -> RatingTable:
        """Ratings of ``handles``; only the handles missing from the cache are requested."""
        async with self._lock:
            now = self._clock()
            keys = {handle_key(h): h for h in handles}
            stale = [
                display
                for key, display in keys.items()
                if (entry := self._cache.get(key)) is None
                or now - entry[1] >= TTL_S
                or (refresh and now - entry[1] >= MIN_REFRESH_AGE_S)
            ]
            if stale:
                result = await self._source.fetch_ratings(stale)
                answered = {handle_key(r.handle): r for r in result.ratings}
                for display in stale:
                    key = handle_key(display)
                    self._cache[key] = (answered.get(key), now, display)
                self._fetched_at = self._now()
                if len(self._cache) > MAX_CACHED:
                    for old in sorted(self._cache, key=lambda k: self._cache[k][1])[:500]:
                        del self._cache[old]
            rows: list[UserRating] = []
            unknown: list[str] = []
            for key, display in keys.items():
                entry = self._cache.get(key)
                if entry is None or entry[0] is None:
                    unknown.append(display)
                else:
                    rows.append(entry[0])
            return RatingTable(tuple(sorted(rows, key=sort_key)), tuple(unknown), self._fetched_at)

    async def card(self, handle: str) -> RatingCard | None:
        """The card of one handle, or ``None`` when Codeforces does not know it."""
        key = handle_key(handle)
        now = self._clock()
        cached = self._cards.get(key)
        if cached is not None and now - cached[1] < TTL_S:
            return cached[0]
        result = await self._source.fetch_ratings([handle])
        if not result.ratings:
            card = None
        else:
            user = result.ratings[0]
            history = await self._source.fetch_rating_history(user.handle)
            card = RatingCard(user, len(history), history[-1] if history else None)
        if len(self._cards) > MAX_CACHED:
            self._cards.clear()
        self._cards[key] = (card, now)
        return card
