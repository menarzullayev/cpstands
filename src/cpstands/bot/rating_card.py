"""``/rating <handle>``: a rating card for one Codeforces user, with a follow button."""

from __future__ import annotations

import html
import re

import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)

from cpstands.bot import keyboards
from cpstands.bot.common import ensure_chat, say, tap_context
from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.domain.contest import handle_key
from cpstands.i18n import Markup, Translator
from cpstands.services.ratings import RatingCard
from cpstands.services.watchlist import PLATFORM, parse_handles
from cpstands.sources.base import SourceError

log = structlog.get_logger(__name__)

FOLLOW_PREFIX = "rt:add:"
PROFILE_URL = "https://codeforces.com/profile/{handle}"
_KEY_RE = re.compile(r"^[a-z0-9_.-]{1,24}$")


def card_text(tr: Translator, card: RatingCard) -> str:
    user = card.user
    link = Markup(
        f'<a href="{html.escape(PROFILE_URL.format(handle=user.handle), quote=True)}">'
        f"{html.escape(user.handle, quote=False)}</a>"
    )
    lines: list[str] = []
    if user.rating is None:
        lines.append(tr("rating-unrated"))
    else:
        lines.append(
            tr(
                "rating-line",
                rating=str(user.rating),
                max=str(user.max_rating if user.max_rating is not None else user.rating),
                rank=user.rank or "-",
            )
        )
    if card.contests:
        lines.append(tr("rating-contests", count=card.contests))
    else:
        lines.append(tr("rating-no-contests"))
    if card.last is not None:
        last = card.last
        lines.append(
            tr(
                "rating-last",
                contest=last.contest_name,
                delta=f"{last.delta:+d}",
                old=str(last.old_rating),
                new=str(last.new_rating),
            )
        )
    return tr("rating-card", handle=link, body=Markup("\n".join(lines)))


def card_keyboard(
    tr: Translator, handle: str, *, followed: bool, icons: bool
) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    if not followed:
        row.append(
            keyboards.button(
                tr("button-follow"),
                f"{FOLLOW_PREFIX}{handle_key(handle)}",
                emoji="2795",
                style="success",
                icons=icons,
            )
        )
    row.append(
        keyboards.link(
            tr("button-profile"),
            PROFILE_URL.format(handle=handle),
            emoji="🔗",
            icons=icons,
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[row])


async def _is_followed(deps: Deps, chat_id: int, key: str) -> bool:
    async with deps.sessions() as session:
        return await repos.get_friend(session, chat_id, PLATFORM, key) is not None


async def on_rating(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    tr = say(deps, chat)
    parsed = parse_handles(command.args or "", max_items=1)
    if not parsed.valid:
        await deps.whisper.reply(message, tr("rating-usage"))
        return
    handle = parsed.valid[0]
    await message.bot.send_chat_action(message.chat.id, "typing")  # type: ignore[union-attr]
    try:
        card = await deps.ratings.card(handle)
    except SourceError:
        log.warning("rating_source_error", exc_info=True)
        await deps.whisper.reply(message, tr("rating-source-error"))
        return
    if card is None:
        await deps.whisper.reply(message, tr("rating-not-found", handle=handle))
        return
    followed = await _is_followed(deps, chat.chat_id, handle_key(card.user.handle))
    await message.answer(
        card_text(tr, card),
        reply_markup=card_keyboard(tr, card.user.handle, followed=followed, icons=deps.icons),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def on_follow(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    tr = say(deps, chat)
    key = (callback.data or "")[len(FOLLOW_PREFIX) :]
    if not _KEY_RE.match(key):
        await callback.answer(tr("button-expired"), show_alert=True)
        return
    try:
        result = await deps.watchlist.add(chat.chat_id, key)
    except SourceError:
        await callback.answer(tr("rating-source-error"), show_alert=True)
        return
    if result.over_limit:
        await callback.answer(
            tr("rating-follow-limit", limit=deps.watchlist.limit), show_alert=True
        )
        return
    if result.unknown or result.invalid:
        await callback.answer(tr("rating-not-found", handle=key), show_alert=True)
        return
    profile = keyboards.link(
        tr("button-profile"), PROFILE_URL.format(handle=key), emoji="🔗", icons=deps.icons
    )
    await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[profile]]))
    await callback.answer(tr("rating-follow-done"))


def create_rating_router() -> Router:
    router = Router(name="rating")
    router.message.register(on_rating, Command("rating"))
    router.callback_query.register(on_follow, F.data.startswith(FOLLOW_PREFIX))
    return router
