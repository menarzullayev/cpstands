"""``/app``: a button that opens the Mini App; in a group, the group's own signed view."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, Message

from cpstands.bot import keyboards
from cpstands.bot.common import ensure_chat, say
from cpstands.bot.deps import Deps


async def on_app(message: Message, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    tr = say(deps, chat)
    group = message.chat.type != "private"
    button = keyboards.app_button(tr, "home", icons=deps.icons, chat_id=message.chat.id)
    await message.answer(
        tr("app-text-group") if group else tr("app-text"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )


def create_app_router() -> Router:
    router = Router(name="app")
    router.message.register(on_app, Command("app"))
    return router
