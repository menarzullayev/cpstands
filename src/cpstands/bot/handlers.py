"""Handlers for onboarding, settings, time zone, the watch list, help and chat membership."""

from __future__ import annotations

import re

import structlog
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InputRichMessage,
    LinkPreviewOptions,
    Message,
)

from cpstands import platforms
from cpstands.bot import keyboards, rank_view, standings_view
from cpstands.bot.common import CHAT_TYPES
from cpstands.bot.common import ensure_chat as _ensure_chat
from cpstands.bot.common import is_admin as _is_admin
from cpstands.bot.common import refresh as _refresh
from cpstands.bot.common import say as _say
from cpstands.bot.common import tap_context as _tap_context
from cpstands.bot.deps import Deps, PlatformKit
from cpstands.bot.live import MAX_LIVE_PER_CHAT
from cpstands.bot.reminders import duration_text, tg_time
from cpstands.bot.settings import settings_view as _settings_view
from cpstands.db import repos
from cpstands.domain.contest import ContestPhase, FullStandings
from cpstands.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, Markup, Translator
from cpstands.services import timezone as tzs
from cpstands.services.watchlist import INPUT_CAP, PLATFORM
from cpstands.sources.base import PermanentSourceError, SourceError

log = structlog.get_logger(__name__)

# The party popper effect; Telegram plays it only in private chats.
CELEBRATE_EFFECT_ID = "5046509860389126442"

_CHAT_TYPES = CHAT_TYPES
_JOINED = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}
_GONE = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}


# --- views -------------------------------------------------------------------------------


def _zone_step(deps: Deps, chat: repos.ChatRecord) -> tuple[str, InlineKeyboardMarkup]:
    say = _say(deps, chat)
    text = f"{say('onboarding-intro')}\n\n{say('onboarding-pick-timezone')}"
    markup = keyboards.timezone_keyboard(
        tzs.popular_zones(chat.language), chat.time_zone, icons=deps.icons
    )
    return text, markup


# --- onboarding --------------------------------------------------------------------------


async def on_start(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    user_id = message.from_user.id if message.from_user else None
    if not await _is_admin(deps, message.chat, user_id):
        await deps.whisper.reply(message, _say(deps, chat)("setup-admin-needed"))
        return
    await message.answer(
        deps.i18n.t(None, "pick-language"),
        reply_markup=keyboards.language_keyboard(chat.language, icons=deps.icons),
    )


async def on_language_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    code = (callback.data or "")[len(keyboards.LANG_PREFIX) :]
    if code not in SUPPORTED_LANGUAGES:
        await callback.answer(_say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_language(session, chat.chat_id, code)
    updated = await _refresh(deps, chat.chat_id)
    if updated.status == "onboarding":
        text, markup = _zone_step(deps, updated)
    else:
        text, markup = await _settings_view(deps, updated)
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def on_zone_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    zone = (callback.data or "")[len(keyboards.TZ_PREFIX) :]
    if not tzs.is_valid_zone(zone):
        await callback.answer(_say(deps, chat)("timezone-invalid-button"), show_alert=True)
        return
    finishing = chat.status == "onboarding" and chat.language is not None
    async with deps.sessions() as session, session.begin():
        await repos.set_time_zone(session, chat.chat_id, zone)
        if finishing:
            await repos.set_status(session, chat.chat_id, "active")
    updated = await _refresh(deps, chat.chat_id)
    say = _say(deps, updated)
    if finishing:
        await deps.contests.plan()
        language = LANGUAGE_NAMES[updated.language or "uz"]
        await message.edit_text(say("setup-done", language=language, zone=zone))
        if message.chat.type == "private" and updated.tone == "playful":
            await message.answer(say("setup-celebrate"), message_effect_id=CELEBRATE_EFFECT_ID)
    elif chat.status == "onboarding":
        await message.edit_text(say("timezone-set", zone=zone, time=tzs.local_time_text(zone)))
    else:
        text, markup = await _settings_view(deps, updated)
        await message.edit_text(text, reply_markup=markup)
    await callback.answer()


# --- time zone, settings, tone -----------------------------------------------------------


async def on_timezone(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    user_id = message.from_user.id if message.from_user else None
    if not await _is_admin(deps, message.chat, user_id):
        await deps.whisper.reply(message, say("not-admin"))
        return
    query = (command.args or "").strip()
    if not query:
        await message.answer(
            say("onboarding-pick-timezone"),
            reply_markup=keyboards.timezone_keyboard(
                tzs.popular_zones(chat.language), chat.time_zone, icons=deps.icons
            ),
        )
        return
    shown = query[: tzs.MAX_QUERY_LENGTH]
    result = tzs.resolve(query)
    if result.kind == "exact":
        zone = result.zones[0]
        async with deps.sessions() as session, session.begin():
            await repos.set_time_zone(session, chat.chat_id, zone)
        await message.answer(say("timezone-set", zone=zone, time=tzs.local_time_text(zone)))
    elif result.kind == "choices":
        await message.answer(
            say("timezone-choose", query=shown),
            reply_markup=keyboards.timezone_keyboard(result.zones, icons=deps.icons),
        )
    else:
        await deps.whisper.reply(message, say("timezone-not-found", query=shown))


# --- upcoming contests -------------------------------------------------------------------


async def on_upcoming(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    contests: list[tuple[platforms.Platform, repos.ContestRow]] = []
    failed = 0
    for name, kit in deps.kits().items():
        try:
            found = await kit.contests.upcoming()
        except SourceError:
            log.warning("upcoming_source_error", platform=name, exc_info=True)
            failed += 1
            continue
        contests.extend((platforms.get(name), c) for c in found)
    if failed and not contests:
        await deps.whisper.reply(message, say("upcoming-source-error"))
        return
    contests.sort(key=lambda pc: (pc[1].starts_at is None, pc[1].starts_at, pc[0].name))
    if not contests:
        await deps.whisper.reply(message, say("upcoming-empty"))
        return
    blocks = [say("upcoming-header")]
    for site, contest in contests:
        label = f" · {site.label}" if site.prefix else ""
        name = Markup(
            f'<a href="{site.contest_url(contest.contest_id)}">'
            f"{_escape(contest.name)}</a>{_escape(label)}"
        )
        assert contest.starts_at is not None  # upcoming contests always have a start
        blocks.append(
            say(
                "upcoming-line",
                name=name,
                start=tg_time(contest.starts_at, chat.time_zone),
                duration=duration_text(contest.duration_s),
            )
        )
    await message.answer(
        "\n\n".join(blocks), link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


# --- watch list --------------------------------------------------------------------------


async def on_track(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    verb, _, rest = (command.args or "").strip().partition(" ")
    verb = verb.lower()
    if verb == "list":
        handles = await deps.watchlist.list_all(chat.chat_id)
        if not handles:
            await deps.whisper.reply(message, say("track-list-empty"))
        else:
            header = say("track-list-header", count=len(handles))
            names = ", ".join(f"<code>{_escape(h)}</code>" for h in handles)
            await message.answer(f"{header}\n{names}")
        return
    if verb not in {"add", "remove"}:
        await deps.whisper.reply(message, say("track-usage"))
        return
    user_id = message.from_user.id if message.from_user else None
    if not await _is_admin(deps, message.chat, user_id):
        await deps.whisper.reply(message, say("not-admin"))
        return
    if not rest.strip():
        await deps.whisper.reply(message, say("track-nothing"))
        return
    try:
        lines = await (_add if verb == "add" else _remove)(deps, chat, rest)
    except SourceError:
        log.warning("track_source_error", exc_info=True)
        await deps.whisper.reply(message, say("track-source-error"))
        return
    await message.answer("\n".join(lines) if lines else say("track-nothing"))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _add(deps: Deps, chat: repos.ChatRecord, text: str) -> list[str]:
    result = await deps.watchlist.add(chat.chat_id, text)
    say = _say(deps, chat)
    lines: list[str] = []
    if result.added:
        lines.append(say("track-added", handles=", ".join(result.added)))
    if result.already:
        lines.append(say("track-already", handles=", ".join(result.already)))
    if result.unknown:
        lines.append(say("track-unknown", handles=", ".join(result.unknown)))
    if result.invalid:
        lines.append(say("track-invalid", handles=", ".join(result.invalid)))
    if result.over_limit:
        handles = ", ".join(result.over_limit)
        lines.append(say("track-limit", limit=deps.watchlist.limit, handles=handles))
    if result.truncated:
        lines.append(say("track-truncated", limit=INPUT_CAP))
    return lines


async def _remove(deps: Deps, chat: repos.ChatRecord, text: str) -> list[str]:
    result = await deps.watchlist.remove(chat.chat_id, text)
    say = _say(deps, chat)
    lines: list[str] = []
    if result.removed:
        lines.append(say("track-removed", handles=", ".join(result.removed)))
    if result.not_found:
        lines.append(say("track-not-found", handles=", ".join(result.not_found)))
    return lines


# --- help and commands that are not built yet --------------------------------------------


async def on_help(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    await message.answer(
        say("help-text"), reply_markup=keyboards.help_keyboard(say, icons=deps.icons)
    )


async def on_help_settings(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=False)
    if context is None:
        return
    message, chat = context
    text, markup = await _settings_view(deps, chat)
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def on_help_track(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=False)
    if context is None:
        return
    message, chat = context
    await message.edit_text(_say(deps, chat)("track-usage"))
    await callback.answer()


# --- friends' ratings --------------------------------------------------------------------


async def _rank_page(
    deps: Deps,
    chat: repos.ChatRecord,
    page: int,
    *,
    refresh: bool,
    platform: str = PLATFORM,
) -> tuple[str, InlineKeyboardMarkup] | str:
    """The rating page and its buttons, or the text of a failure."""
    say = _say(deps, chat)
    kit = deps.kit(platform)
    handles = await deps.watchlist.list(chat.chat_id, platform)
    if not handles or kit is None:
        return say("rank-empty")
    try:
        table = await kit.ratings.get(handles, refresh=refresh)
    except SourceError:
        log.warning("rank_source_error", platform=platform, exc_info=True)
        return say("rank-source-error")
    site = platforms.get(platform)
    text = rank_view.render(table, page, say, time_zone=chat.time_zone, site=site)
    return text, rank_view.keyboard(len(table.rows), page, say, icons=deps.icons, site=site)


def _rank_platform(arg: str) -> str:
    """``/rank`` is Codeforces; ``/rank kep`` (or ``kep:``) is kep.uz."""
    word = arg.strip().lower().rstrip(":")
    for name, site in platforms.PLATFORMS.items():
        if word and word in {name, site.prefix.rstrip(":"), site.label.lower()}:
            return name
    return PLATFORM


async def on_rank(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    await message.bot.send_chat_action(message.chat.id, "typing")  # type: ignore[union-attr]
    platform = _rank_platform(command.args or "")
    result = await _rank_page(deps, chat, 0, refresh=False, platform=platform)
    if isinstance(result, str):
        await deps.whisper.reply(message, result)
        return
    text, markup = result
    await message.bot.send_rich_message(  # type: ignore[union-attr]
        message.chat.id,
        InputRichMessage(html=text),
        reply_markup=markup,
        message_thread_id=message.message_thread_id if message.is_topic_message else None,
    )


async def on_rank_page(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=False)
    if context is None:
        return
    message, chat = context
    parts = (callback.data or "").split(":")
    try:
        page = int(parts[1])
    except (IndexError, ValueError):
        await callback.answer(_say(deps, chat)("button-expired"), show_alert=True)
        return
    platform = rank_view.platform_of(parts)
    refresh = "r" in parts[2:]
    result = await _rank_page(deps, chat, page, refresh=refresh, platform=platform)
    if isinstance(result, str):
        await callback.answer(_plain(result), show_alert=True)
        return
    text, markup = result
    try:
        await message.bot.edit_message_text(  # type: ignore[union-attr]
            chat_id=message.chat.id,
            message_id=message.message_id,
            rich_message=InputRichMessage(html=text),
            reply_markup=markup,
        )
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc):
            raise
    await callback.answer()


async def on_rank_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# --- membership --------------------------------------------------------------------------


async def on_my_chat_member(event: ChatMemberUpdated, deps: Deps) -> None:
    chat = event.chat
    if chat.type not in _CHAT_TYPES:
        return
    new_status = event.new_chat_member.status
    if new_status in _JOINED:
        record = await _ensure_chat(deps, chat)
        fresh = event.old_chat_member.status in _GONE
        if record is not None and chat.type != "private" and fresh:
            await event.answer(_say(deps, record)("group-added"))
    elif new_status in _GONE:
        async with deps.sessions() as session, session.begin():
            await repos.set_status(session, chat.id, "removed")
        deps.admin.invalidate_chat(chat.id)


async def on_chat_member(event: ChatMemberUpdated, deps: Deps) -> None:
    deps.admin.invalidate(event.chat.id, event.new_chat_member.user.id)


# --- standings ---------------------------------------------------------------------------


def parse_contest_id(text: str) -> int | None:
    """Accept ``1970`` or a codeforces.com contest link (Codeforces only)."""
    found = platforms.parse_contest(text)
    return found[1] if found and found[0].name == PLATFORM else None


async def on_standings(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    found = platforms.parse_contest(command.args or "")
    kit = deps.kit(found[0].name) if found else None
    if found is None or kit is None:
        await deps.whisper.reply(message, say("standings-usage"))
        return
    site, contest_id = found
    await message.bot.send_chat_action(message.chat.id, "typing")  # type: ignore[union-attr]
    standings = await _load_standings(kit, contest_id)
    if isinstance(standings, str):
        await deps.whisper.reply(message, _failure(say, standings, site.shown(contest_id)))
        return
    if standings.contest.phase is ContestPhase.BEFORE:
        await message.answer(say("standings-not-started", name=standings.contest.name))
        return
    ctx = await _view_context(deps, chat, None, site.name)
    text = standings_view.render(standings, 0, 0, say, time_zone=chat.time_zone, ctx=ctx)
    markup = standings_view.keyboard(
        standings, 0, 0, say, icons=deps.icons, ctx=ctx, chat_id=message.chat.id
    )
    sent = await message.bot.send_rich_message(  # type: ignore[union-attr]
        message.chat.id,
        InputRichMessage(html=text),
        reply_markup=markup,
        message_thread_id=message.message_thread_id if message.is_topic_message else None,
    )
    if standings.contest.phase.is_active:
        async with deps.sessions() as session, session.begin():
            await repos.register_live_message(
                session,
                message.chat.id,
                site.name,
                contest_id,
                sent.message_id,
                max_live=MAX_LIVE_PER_CHAT,
            )


async def _view_context(
    deps: Deps, chat: repos.ChatRecord, preferred: str | None, platform: str = PLATFORM
) -> standings_view.ViewContext:
    """Friends or everyone, and how many problem columns, for this chat."""
    async with deps.sessions() as session:
        friends = frozenset(await repos.scoreboard_keys(session, chat.chat_id, platform))
    view = standings_view.resolve_view(preferred, friends)
    return standings_view.ViewContext(view, friends, chat.table_cols, chat.table_style)


async def _load_standings(
    kit: PlatformKit, contest_id: int, *, refresh: bool = False
) -> FullStandings | str:
    """Return the standings, or the name of a failure: ``not-found`` or ``source-error``."""
    try:
        return await kit.standings.get(contest_id, refresh=refresh)
    except PermanentSourceError:
        return "not-found"
    except SourceError:
        log.warning("standings_source_error", contest_id=contest_id, exc_info=True)
        return "source-error"


def _failure(say: Translator, kind: str, contest_id: int | str) -> str:
    if kind == "not-found":
        return say("standings-not-found", id=str(contest_id))
    return say("standings-source-error")


async def on_standings_page(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=False)
    if context is None:
        return
    message, chat = context
    say = _say(deps, chat)
    parts = (callback.data or "").split(":")
    target = standings_view.parse_target(parts[1] if len(parts) > 1 else "")
    kit = deps.kit(target[0].name) if target else None
    try:
        row_page, col_page = int(parts[2]), int(parts[3])
    except (IndexError, ValueError):
        target = None
    if target is None or kit is None:
        await callback.answer(say("button-expired"), show_alert=True)
        return
    site, contest_id = target
    token = parts[4] if len(parts) > 4 and parts[4] in standings_view.TOKEN_VIEW else None
    preferred = standings_view.TOKEN_VIEW.get(token or "")
    standings = await _load_standings(kit, contest_id, refresh=parts[-1] == "r")
    if isinstance(standings, str):
        await callback.answer(
            _plain(_failure(say, standings, site.shown(contest_id))), show_alert=True
        )
        return
    ctx = await _view_context(deps, chat, preferred, site.name)
    text = standings_view.render(
        standings, row_page, col_page, say, time_zone=chat.time_zone, ctx=ctx
    )
    markup = standings_view.keyboard(
        standings, row_page, col_page, say, icons=deps.icons, ctx=ctx, chat_id=chat.chat_id
    )
    if standings.contest.phase.is_active:
        async with deps.sessions() as session, session.begin():
            await repos.set_live_pages(
                session,
                message.chat.id,
                site.name,
                contest_id,
                message.message_id,
                row_page,
                col_page,
                ctx.view if preferred else "auto",
            )
    try:
        await message.bot.edit_message_text(  # type: ignore[union-attr]
            chat_id=message.chat.id,
            message_id=message.message_id,
            rich_message=InputRichMessage(html=text),
            reply_markup=markup,
        )
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc):
            raise
    await callback.answer()


def _plain(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text)


async def on_standings_noop(callback: CallbackQuery) -> None:
    await callback.answer()


def create_router() -> Router:
    """Build a fresh router; one per dispatcher so tests can build several."""
    router = Router(name="main")
    router.message.register(on_start, Command("start"))
    router.callback_query.register(on_language_chosen, F.data.startswith(keyboards.LANG_PREFIX))
    router.callback_query.register(on_zone_chosen, F.data.startswith(keyboards.TZ_PREFIX))
    router.message.register(on_upcoming, Command("upcoming"))
    router.message.register(on_timezone, Command("timezone"))
    router.callback_query.register(on_help_settings, F.data == keyboards.HELP_SETTINGS)
    router.callback_query.register(on_help_track, F.data == keyboards.HELP_TRACK)
    router.message.register(on_track, Command("track", "friends"))
    router.message.register(on_standings, Command("standings"))
    router.callback_query.register(on_standings_noop, F.data == standings_view.NOOP)
    router.callback_query.register(
        on_standings_page, F.data.startswith(standings_view.CALLBACK_PREFIX)
    )
    router.message.register(on_help, Command("help"))
    router.message.register(on_rank, Command("rank"))
    router.callback_query.register(on_rank_noop, F.data == rank_view.NOOP)
    router.callback_query.register(on_rank_page, F.data.startswith(rank_view.PREFIX))
    router.my_chat_member.register(on_my_chat_member)
    router.chat_member.register(on_chat_member)
    return router
