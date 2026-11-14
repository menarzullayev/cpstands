"""Who may change a chat's settings: group admins only, checked against Telegram (stage 06)."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog

ADMIN_CACHE_TTL_S = 300.0
ADMIN_STATUSES = frozenset({"creator", "administrator"})
# Telegram shows messages sent "as the group" by an anonymous admin from this fixed user.
ANONYMOUS_ADMIN_ID = 1087968824

type MemberStatusFetcher = Callable[[int, int], Awaitable[str]]

log = structlog.get_logger(__name__)


class AdminChecker:
    """Answers "is this user an admin of this chat?" with a short cache.

    The answer is cached for five minutes and dropped early when a ``chat_member`` update
    arrives. Any failure to ask Telegram counts as "not an admin" and is never cached.
    """

    def __init__(
        self,
        fetch_status: MemberStatusFetcher,
        *,
        ttl_s: float = ADMIN_CACHE_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch_status = fetch_status
        self._ttl_s = ttl_s
        self._clock = clock
        self._cache: dict[tuple[int, int], tuple[bool, float]] = {}

    async def is_admin(self, chat_id: int, user_id: int, *, private: bool = False) -> bool:
        if private:
            return True
        if user_id == ANONYMOUS_ADMIN_ID:
            return True
        key = (chat_id, user_id)
        now = self._clock()
        cached = self._cache.get(key)
        if cached is not None and cached[1] > now:
            return cached[0]
        try:
            status = await self._fetch_status(chat_id, user_id)
        except Exception:
            log.warning("admin_check_failed", chat_id=chat_id, exc_info=True)
            return False
        allowed = status in ADMIN_STATUSES
        self._cache[key] = (allowed, now + self._ttl_s)
        return allowed

    def invalidate(self, chat_id: int, user_id: int) -> None:
        self._cache.pop((chat_id, user_id), None)

    def invalidate_chat(self, chat_id: int) -> None:
        for key in [k for k in self._cache if k[0] == chat_id]:
            del self._cache[key]
