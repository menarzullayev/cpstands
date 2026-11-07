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
    Chat,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InputRichMessage,
    LinkPreviewOptions,
    Message,
)

from cpstands.bot import keyboards, standings_view
from cpstands.bot.deps import Deps
from cpstands.bot.live import MAX_LIVE_PER_CHAT
from cpstands.bot.reminders import duration_text, tg_time
from cpstands.db import repos
from cpstands.domain.contest import ContestPhase, FullStandings
from cpstands.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, TONES, Markup, Translator
from cpstands.services import timezone as tzs
from cpstands.services.watchlist import INPUT_CAP, PLATFORM
from cpstands.sources.base import PermanentSourceError, SourceError

log = structlog.get_logger(__name__)

DEFAULT_REMINDER_OFFSETS = (1440, 60, 10)  # minutes before the start

# The party popper effect; Telegram plays it only in private chats.
CELEBRATE_EFFECT_ID = "5046509860389126442"

_CHAT_TYPES = {"private": "private", "group": "group", "supergroup": "supergroup"}
_JOINED = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}
_GONE = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
_PLANNED_COMMANDS = ("rank",)


def _say(deps: Deps, chat: repos.ChatRecord | None) -> Translator:
    if chat is None:
        return deps.i18n.bound(None)
    return deps.i18n.bound(chat.language, chat.tone)


async def _ensure_chat(deps: Deps, chat: Chat) -> repos.ChatRecord | None:
    chat_type = _CHAT_TYPES.get(chat.type)
    if chat_type is None:
        return None
    async with deps.sessions() as session, session.begin():
        return await repos.upsert_chat(session, chat.id, chat_type)


async def _is_admin(deps: Deps, chat: Chat, user_id: int | None) -> bool:
    if user_id is None:
        return False
    return await deps.admin.is_admin(chat.id, user_id, private=chat.type == "private")


async def _tap_context(
    deps: Deps, callback: CallbackQuery, *, admin: bool
) -> tuple[Message, repos.ChatRecord] | None:
    """Resolve the message and chat of a button tap; answer and stop when it is not allowed."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(deps.i18n.t(None, "button-expired"), show_alert=True)
        return None
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return None
    if admin and not await _is_admin(deps, message.chat, callback.from_user.id):
        await callback.answer(_say(deps, chat)("not-admin"), show_alert=True)
        return None
    return message, chat


# --- views -------------------------------------------------------------------------------


async def _settings_view(deps: Deps, chat: repos.ChatRecord) -> tuple[str, InlineKeyboardMarkup]:
    async with deps.sessions() as session:
        count = await repos.count_handles(session, chat.chat_id, PLATFORM)
    say = _say(deps, chat)
    text = say(
        "settings-summary",
        language=LANGUAGE_NAMES.get(chat.language or "", "-"),
        zone=chat.time_zone or say("settings-timezone-unset"),
        mood=chat.tone,
        reminders="on" if chat.reminder_offsets else "off",
        alerts="on" if chat.alerts_enabled else "off",
        count=count,
    )
    markup = keyboards.settings_keyboard(
        say,
        chat.tone,
        icons=deps.icons,
        reminders_on=bool(chat.reminder_offsets),
        alerts_on=chat.alerts_enabled,
    )
    return text, markup


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


async def _refresh(deps: Deps, chat_id: int) -> repos.ChatRecord:
    async with deps.sessions() as session:
        record = await repos.get_chat(session, chat_id)
    assert record is not None  # the chat was upserted a moment ago
    return record


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


async def on_settings(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    text, markup = await _settings_view(deps, chat)
    await message.answer(text, reply_markup=markup)


async def on_menu_language(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await message.edit_text(
        deps.i18n.t(None, "pick-language"),
        reply_markup=keyboards.language_keyboard(chat.language, icons=deps.icons),
    )
    await callback.answer()


async def on_menu_timezone(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await message.edit_text(
        _say(deps, chat)("onboarding-pick-timezone"),
        reply_markup=keyboards.timezone_keyboard(
            tzs.popular_zones(chat.language), chat.time_zone, icons=deps.icons
        ),
    )
    await callback.answer()


async def on_tone_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    tone = (callback.data or "")[len(keyboards.TONE_PREFIX) :]
    if tone not in TONES:
        await callback.answer(_say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_tone(session, chat.chat_id, tone)
    text, markup = await _settings_view(deps, await _refresh(deps, chat.chat_id))
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def on_reminders_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    value = (callback.data or "")[len(keyboards.REMINDERS_PREFIX) :]
    if value not in {"on", "off"}:
        await callback.answer(_say(deps, chat)("button-expired"), show_alert=True)
        return
    offsets = DEFAULT_REMINDER_OFFSETS if value == "on" else ()
    async with deps.sessions() as session, session.begin():
        await repos.set_reminder_offsets(session, chat.chat_id, offsets)
    if offsets:
        await deps.contests.plan()
    text, markup = await _settings_view(deps, await _refresh(deps, chat.chat_id))
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def on_alerts_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await _tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    value = (callback.data or "")[len(keyboards.ALERTS_PREFIX) :]
    if value not in {"on", "off"}:
        await callback.answer(_say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_alerts_enabled(session, chat.chat_id, value == "on")
    text, markup = await _settings_view(deps, await _refresh(deps, chat.chat_id))
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


# --- upcoming contests -------------------------------------------------------------------


async def on_upcoming(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    try:
        contests = await deps.contests.upcoming()
    except SourceError:
        log.warning("upcoming_source_error", exc_info=True)
        await deps.whisper.reply(message, say("upcoming-source-error"))
        return
    if not contests:
        await deps.whisper.reply(message, say("upcoming-empty"))
        return
    blocks = [say("upcoming-header")]
    for contest in contests:
        name = Markup(
            f'<a href="https://codeforces.com/contests/{contest.contest_id}">'
            f"{_escape(contest.name)}</a>"
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
        handles = await deps.watchlist.list(chat.chat_id)
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


async def on_coming_soon(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is not None:
        await deps.whisper.reply(message, _say(deps, chat)("coming-soon"))


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

_CONTEST_URL_RE = re.compile(r"codeforces\.com/(?:contest|contests)/(\d{1,7})", re.IGNORECASE)


def parse_contest_id(text: str) -> int | None:
    """Accept ``1970`` or a codeforces.com contest link."""
    cleaned = text.strip()
    if cleaned.isascii() and cleaned.isdigit() and len(cleaned) <= 7:
        return int(cleaned) or None
    match = _CONTEST_URL_RE.search(cleaned)
    return int(match.group(1)) if match else None


async def on_standings(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    say = _say(deps, chat)
    contest_id = parse_contest_id(command.args or "")
    if contest_id is None:
        await deps.whisper.reply(message, say("standings-usage"))
        return
    await message.bot.send_chat_action(message.chat.id, "typing")  # type: ignore[union-attr]
    standings = await _load_standings(deps, contest_id)
    if isinstance(standings, str):
        await deps.whisper.reply(message, _failure(say, standings, contest_id))
        return
    if standings.contest.phase is ContestPhase.BEFORE:
        await message.answer(say("standings-not-started", name=standings.contest.name))
        return
    text = standings_view.render(standings, 0, 0, say, time_zone=chat.time_zone)
    markup = standings_view.keyboard(standings, 0, 0, say, icons=deps.icons)
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
                PLATFORM,
                contest_id,
                sent.message_id,
                max_live=MAX_LIVE_PER_CHAT,
            )


async def _load_standings(
    deps: Deps, contest_id: int, *, refresh: bool = False
) -> FullStandings | str:
    """Return the standings, or the name of a failure: ``not-found`` or ``source-error``."""
    try:
        return await deps.standings.get(contest_id, refresh=refresh)
    except PermanentSourceError:
        return "not-found"
    except SourceError:
        log.warning("standings_source_error", contest_id=contest_id, exc_info=True)
        return "source-error"


def _failure(say: Translator, kind: str, contest_id: int) -> str:
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
    try:
        contest_id, row_page, col_page = int(parts[1]), int(parts[2]), int(parts[3])
    except (IndexError, ValueError):
        await callback.answer(say("button-expired"), show_alert=True)
        return
    standings = await _load_standings(deps, contest_id, refresh=parts[4:] == ["r"])
    if isinstance(standings, str):
        await callback.answer(_plain(_failure(say, standings, contest_id)), show_alert=True)
        return
    text = standings_view.render(standings, row_page, col_page, say, time_zone=chat.time_zone)
    markup = standings_view.keyboard(standings, row_page, col_page, say, icons=deps.icons)
    if standings.contest.phase.is_active:
        async with deps.sessions() as session, session.begin():
            await repos.set_live_pages(
                session,
                message.chat.id,
                PLATFORM,
                contest_id,
                message.message_id,
                row_page,
                col_page,
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
    router.callback_query.register(on_tone_chosen, F.data.startswith(keyboards.TONE_PREFIX))
    router.callback_query.register(
        on_reminders_chosen, F.data.startswith(keyboards.REMINDERS_PREFIX)
    )
    router.callback_query.register(on_alerts_chosen, F.data.startswith(keyboards.ALERTS_PREFIX))
    router.message.register(on_upcoming, Command("upcoming"))
    router.message.register(on_timezone, Command("timezone"))
    router.message.register(on_settings, Command("settings"))
    router.callback_query.register(on_menu_language, F.data == keyboards.MENU_LANG)
    router.callback_query.register(on_menu_timezone, F.data == keyboards.MENU_TZ)
    router.callback_query.register(on_help_settings, F.data == keyboards.HELP_SETTINGS)
    router.callback_query.register(on_help_track, F.data == keyboards.HELP_TRACK)
    router.message.register(on_track, Command("track", "friends"))
    router.message.register(on_standings, Command("standings"))
    router.callback_query.register(on_standings_noop, F.data == standings_view.NOOP)
    router.callback_query.register(
        on_standings_page, F.data.startswith(standings_view.CALLBACK_PREFIX)
    )
    router.message.register(on_help, Command("help"))
    router.message.register(on_coming_soon, Command(*_PLANNED_COMMANDS))
    router.my_chat_member.register(on_my_chat_member)
    router.chat_member.register(on_chat_member)
    return router
