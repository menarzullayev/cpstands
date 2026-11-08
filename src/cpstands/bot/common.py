"""Helpers shared by the handler modules."""

from __future__ import annotations

from aiogram.types import CallbackQuery, Chat, Message

from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.i18n import Translator

CHAT_TYPES = {"private": "private", "group": "group", "supergroup": "supergroup"}
DEFAULT_REMINDER_OFFSETS = (1440, 60, 10)  # minutes before the start


def say(deps: Deps, chat: repos.ChatRecord | None) -> Translator:
    if chat is None:
        return deps.i18n.bound(None)
    return deps.i18n.bound(chat.language, chat.tone)


async def ensure_chat(deps: Deps, chat: Chat) -> repos.ChatRecord | None:
    chat_type = CHAT_TYPES.get(chat.type)
    if chat_type is None:
        return None
    async with deps.sessions() as session, session.begin():
        return await repos.upsert_chat(session, chat.id, chat_type)


async def is_admin(deps: Deps, chat: Chat, user_id: int | None) -> bool:
    if user_id is None:
        return False
    return await deps.admin.is_admin(chat.id, user_id, private=chat.type == "private")


async def tap_context(
    deps: Deps, callback: CallbackQuery, *, admin: bool
) -> tuple[Message, repos.ChatRecord] | None:
    """Resolve the message and chat of a button tap; answer and stop when it is not allowed."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(deps.i18n.t(None, "button-expired"), show_alert=True)
        return None
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return None
    if admin and not await is_admin(deps, message.chat, callback.from_user.id):
        await callback.answer(say(deps, chat)("not-admin"), show_alert=True)
        return None
    return message, chat


async def refresh(deps: Deps, chat_id: int) -> repos.ChatRecord:
    async with deps.sessions() as session:
        record = await repos.get_chat(session, chat_id)
    assert record is not None  # the chat was upserted a moment ago
    return record
