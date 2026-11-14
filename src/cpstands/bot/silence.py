"""Silent chats: updates from these chats are dropped before any handler, so nothing is sent.

Used for a group the bot was added to before its owners agreed to any message there.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message, TelegramObject

log = structlog.get_logger(__name__)


def chat_of(event: TelegramObject) -> int | None:
    if isinstance(event, Message | ChatMemberUpdated):
        return event.chat.id
    if isinstance(event, CallbackQuery) and isinstance(event.message, Message):
        return event.message.chat.id
    return None


class SilenceMiddleware(BaseMiddleware):
    def __init__(self, chats: Iterable[int]) -> None:
        self._chats = frozenset(chats)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id = chat_of(event)
        if chat_id is not None and chat_id in self._chats:
            log.info("silent_chat_update_dropped", kind=type(event).__name__)
            return None
        return await handler(event, data)
