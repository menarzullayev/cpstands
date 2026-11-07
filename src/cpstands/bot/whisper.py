"""Ephemeral replies (Bot API 10.2): in groups, helper answers are visible only to the asker.

Telegram accepts them only when the bot is an admin of the chat. Anywhere else, and on any
refusal, the reply goes out as a normal message, so nothing is ever lost.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import structlog
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import EphemeralMessageParameters, InlineKeyboardMarkup, Message

log = structlog.get_logger(__name__)

RETRY_AFTER_S = 600.0


class Whisper:
    def __init__(
        self, *, enabled: bool = True, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._enabled = enabled
        self._clock = clock
        self._blocked_until: dict[int, float] = {}

    async def reply(
        self, message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
    ) -> None:
        user = message.from_user
        chat = message.chat
        if (
            not self._enabled
            or user is None
            or chat.type not in {"group", "supergroup"}
            or self._blocked_until.get(chat.id, 0.0) > self._clock()
        ):
            await message.answer(text, reply_markup=reply_markup)
            return
        try:
            await message.bot.send_message(  # type: ignore[union-attr]
                chat.id,
                text,
                reply_markup=reply_markup,
                message_thread_id=message.message_thread_id if message.is_topic_message else None,
                ephemeral_message_parameters=EphemeralMessageParameters(receiver_user_id=user.id),
            )
        except TelegramBadRequest as exc:
            # Usually BOT_NOT_ADMIN; do not retry for a while.
            log.info("ephemeral_refused", chat_id=chat.id, reason=str(exc)[:80])
            self._blocked_until[chat.id] = self._clock() + RETRY_AFTER_S
            await message.answer(text, reply_markup=reply_markup)
