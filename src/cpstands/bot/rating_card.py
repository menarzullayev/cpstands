"""``/rating <handle>``: a rating card for one Codeforces or kep.uz user, with a follow button."""

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

from cpstands import platforms
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
FOLLOW_EMOJI = chr(0x2795)  # heavy plus sign
PROFILE_URL = "https://codeforces.com/profile/{handle}"
_KEY_RE = re.compile(r"^(?:[a-z]{1,8}:)?[a-z0-9_.-]{1,24}$")


def card_text(
    tr: Translator, card: RatingCard, site: platforms.Platform = platforms.DEFAULT
) -> str:
    user = card.user
    link = Markup(
        f'<a href="{html.escape(site.profile_url(user.handle), quote=True)}">'
        f"{html.escape(site.shown(user.handle), quote=False)}</a>"
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


def app_route(site: platforms.Platform, handle: str) -> str:
    """The Mini App page of a handle: ``profile_tourist`` or ``kprofile_alice``."""
    return f"{site.prefix.rstrip(':')[:1]}profile_{handle}"


def card_keyboard(
    tr: Translator,
    handle: str,
    *,
    followed: bool,
    icons: bool,
    site: platforms.Platform = platforms.DEFAULT,
) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    if not followed:
        row.append(
            keyboards.button(
                tr("button-follow"),
                f"{FOLLOW_PREFIX}{site.shown(handle_key(handle))}",
                emoji=FOLLOW_EMOJI,
                style="success",
                icons=icons,
            )
        )
    row.append(
        keyboards.link(
            tr("button-profile"),
            site.profile_url(handle),
            emoji="🔗",
            icons=icons,
        )
    )
    app = keyboards.app_button(tr, app_route(site, handle), icons=icons)
    return InlineKeyboardMarkup(inline_keyboard=[row, [app]])


async def _is_followed(deps: Deps, chat_id: int, key: str, platform: str = PLATFORM) -> bool:
    async with deps.sessions() as session:
        return await repos.get_friend(session, chat_id, platform, key) is not None


async def on_rating(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    tr = say(deps, chat)
    parsed = parse_handles(command.args or "", max_items=1)
    if not parsed.valid:
        await deps.whisper.reply(message, tr("rating-usage"))
        return
    site, handle = platforms.split(parsed.valid[0])
    kit = deps.kit(site.name)
    if kit is None:
        await deps.whisper.reply(message, tr("rating-usage"))
        return
    await message.bot.send_chat_action(message.chat.id, "typing")  # type: ignore[union-attr]
    try:
        card = await kit.ratings.card(handle)
    except SourceError:
        log.warning("rating_source_error", exc_info=True)
        await deps.whisper.reply(message, tr("rating-source-error"))
        return
    if card is None:
        await deps.whisper.reply(message, tr("rating-not-found", handle=site.shown(handle)))
        return
    key = handle_key(card.user.handle)
    followed = await _is_followed(deps, chat.chat_id, key, site.name)
    markup = card_keyboard(tr, card.user.handle, followed=followed, icons=deps.icons, site=site)
    await message.answer(
        card_text(tr, card, site),
        reply_markup=markup,
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
    site, bare = platforms.split(key)
    profile = keyboards.link(
        tr("button-profile"), site.profile_url(bare), emoji="🔗", icons=deps.icons
    )
    await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[profile]]))
    await callback.answer(tr("rating-follow-done"))


def create_rating_router() -> Router:
    router = Router(name="rating")
    router.message.register(on_rating, Command("rating"))
    router.callback_query.register(on_follow, F.data.startswith(FOLLOW_PREFIX))
    return router
