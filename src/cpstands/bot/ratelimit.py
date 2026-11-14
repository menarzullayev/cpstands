"""Per-user and per-chat command rate limits (stage 08): 20 and 60 per minute."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from cpstands.bot.deps import Deps

Verdict = Literal["ok", "first_over", "over"]

PER_USER_LIMIT = 20
PER_CHAT_LIMIT = 60
WINDOW_S = 60.0
_PRUNE_AT = 5000


class RateLimiter:
    """Sliding-window counter. ``first_over`` is reported once so the user is told only once."""

    def __init__(
        self,
        *,
        per_user: int = PER_USER_LIMIT,
        per_chat: int = PER_CHAT_LIMIT,
        window_s: float = WINDOW_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._per_user = per_user
        self._per_chat = per_chat
        self._window_s = window_s
        self._clock = clock
        self._hits: dict[tuple[str, int], deque[float]] = {}
        self._notified: set[tuple[str, int]] = set()

    def check(self, user_id: int, chat_id: int) -> Verdict:
        now = self._clock()
        if len(self._hits) > _PRUNE_AT:
            self._prune(now)
        user_key, chat_key = ("u", user_id), ("c", chat_id)
        user_over = self._over(user_key, self._per_user, now)
        chat_over = self._over(chat_key, self._per_chat, now)
        if not (user_over or chat_over):
            self._notified.discard(user_key)
            return "ok"
        if user_key in self._notified:
            return "over"
        self._notified.add(user_key)
        return "first_over"

    def _over(self, key: tuple[str, int], limit: int, now: float) -> bool:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self._window_s:
            hits.popleft()
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - self._window_s]:
            del self._hits[key]
            self._notified.discard(key)


class RateLimitMiddleware(BaseMiddleware):
    """Counts commands and button taps; plain chatter in groups is not counted."""

    def __init__(self, limiter: RateLimiter) -> None:
        self._limiter = limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id, chat_id = self._ids(event)
        if user_id is None or chat_id is None:
            return await handler(event, data)
        verdict = self._limiter.check(user_id, chat_id)
        if verdict == "ok":
            return await handler(event, data)
        if verdict == "first_over":
            deps: Deps = data["deps"]
            text = deps.i18n.t(None, "rate-limited")
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
        return None

    @staticmethod
    def _ids(event: TelegramObject) -> tuple[int | None, int | None]:
        if isinstance(event, Message):
            is_command = bool(event.text and event.text.startswith("/"))
            if not is_command or event.from_user is None:
                return None, None
            return event.from_user.id, event.chat.id
        if isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id if event.message else event.from_user.id
            return event.from_user.id, chat_id
        return None, None
