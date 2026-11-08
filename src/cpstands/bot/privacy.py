"""``/privacy`` and ``/delete``: what is stored, and erasing it after an explicit confirmation."""

from __future__ import annotations

import time

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
)

from cpstands.bot import keyboards
from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.i18n import Translator
from cpstands.services import privacy

log = structlog.get_logger(__name__)

POLICY_URL = "https://github.com/menarzullayev/cpstands/blob/main/PRIVACY.md"
ASK = "del:ask"
YES_PREFIX = "del:yes:"
NO = "del:no"


async def _say(deps: Deps, chat_id: int) -> Translator:
    async with deps.sessions() as session:
        record = await repos.get_chat(session, chat_id)
    return deps.i18n.bound(record.language, record.tone) if record else deps.i18n.bound(None)


async def _is_admin(deps: Deps, chat: Chat, user_id: int) -> bool:
    return await deps.admin.is_admin(chat.id, user_id, private=chat.type == "private")


def _minute() -> int:
    return int(time.time() // 60)


def confirm_keyboard(
    say: Translator, *, icons: bool, minute: int | None = None
) -> InlineKeyboardMarkup:
    stamp = _minute() if minute is None else minute
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                keyboards.button(
                    say("button-delete-yes"),
                    f"{YES_PREFIX}{stamp}",
                    emoji="🗑",
                    style="danger",
                    icons=icons,
                ),
                keyboards.button(say("button-delete-no"), NO, emoji="❌", icons=icons),
            ]
        ]
    )


async def on_privacy(message: Message, deps: Deps) -> None:
    say = await _say(deps, message.chat.id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                keyboards.link(
                    say("button-privacy-policy"), POLICY_URL, emoji="🔒", icons=deps.icons
                ),
                keyboards.button(say("button-delete-data"), ASK, emoji="🗑", icons=deps.icons),
            ]
        ]
    )
    await message.answer(say("privacy-text"), reply_markup=markup)


async def on_delete(message: Message, deps: Deps) -> None:
    say = await _say(deps, message.chat.id)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or not await _is_admin(deps, message.chat, user_id):
        await deps.whisper.reply(message, say("not-admin"))
        return
    await message.answer(
        say("delete-confirm"), reply_markup=confirm_keyboard(say, icons=deps.icons)
    )


async def on_delete_ask(callback: CallbackQuery, deps: Deps) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    say = await _say(deps, message.chat.id)
    if not await _is_admin(deps, message.chat, callback.from_user.id):
        await callback.answer(say("not-admin"), show_alert=True)
        return
    await message.answer(
        say("delete-confirm"), reply_markup=confirm_keyboard(say, icons=deps.icons)
    )
    await callback.answer()


async def on_delete_yes(callback: CallbackQuery, deps: Deps) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    say = await _say(deps, message.chat.id)
    if not await _is_admin(deps, message.chat, callback.from_user.id):
        await callback.answer(say("not-admin"), show_alert=True)
        return
    try:
        issued = int((callback.data or "")[len(YES_PREFIX) :])
    except ValueError:
        await callback.answer(say("button-expired"), show_alert=True)
        return
    if _minute() - issued > privacy.CONFIRM_VALID_S // 60 or issued > _minute() + 1:
        await message.edit_text(say("delete-expired"))
        await callback.answer()
        return
    deleted = await privacy.delete_chat_data(deps.sessions, message.chat.id)
    deps.admin.invalidate_chat(message.chat.id)
    if deleted is None:
        await message.edit_text(say("delete-nothing"))
    else:
        log.info("chat_data_deleted", handles=deleted.handles)
        await message.edit_text(say("delete-done", handles=deleted.handles))
    await callback.answer()


async def on_delete_no(callback: CallbackQuery, deps: Deps) -> None:
    message = callback.message
    if isinstance(message, Message):
        say = await _say(deps, message.chat.id)
        if await _is_admin(deps, message.chat, callback.from_user.id):
            await message.edit_text(say("delete-cancelled"))
        else:
            await callback.answer(say("not-admin"), show_alert=True)
            return
    await callback.answer()


def create_privacy_router() -> Router:
    router = Router(name="privacy")
    router.message.register(on_privacy, Command("privacy"))
    router.message.register(on_delete, Command("delete"))
    router.callback_query.register(on_delete_ask, F.data == ASK)
    router.callback_query.register(on_delete_yes, F.data.startswith(YES_PREFIX))
    router.callback_query.register(on_delete_no, F.data == NO)
    return router
