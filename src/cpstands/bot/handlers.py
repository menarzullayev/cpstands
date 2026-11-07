"""Handlers for onboarding, settings, time zone, the watch list and chat membership."""

from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Chat, ChatMemberUpdated, InlineKeyboardMarkup, Message

from cpstands.bot import keyboards
from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES
from cpstands.services import timezone as tzs
from cpstands.services.watchlist import INPUT_CAP, PLATFORM
from cpstands.sources.base import SourceError

log = structlog.get_logger(__name__)

_CHAT_TYPES = {"private": "private", "group": "group", "supergroup": "supergroup"}
_JOINED = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}
_GONE = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
_PLANNED_COMMANDS = (
    "standings",
    "upcoming",
    "rank",
    "privacy",
    "delete",
    "status",
    "pause",
    "resume",
    "stats",
)


async def _ensure_chat(deps: Deps, chat: Chat) -> repos.ChatRecord | None:
    chat_type = _CHAT_TYPES.get(chat.type)
    if chat_type is None:
        return None
    async with deps.sessions() as session, session.begin():
        return await repos.upsert_chat(session, chat.id, chat_type)


async def _chat_language(deps: Deps, chat_id: int) -> str | None:
    async with deps.sessions() as session:
        record = await repos.get_chat(session, chat_id)
    return record.language if record else None


async def _is_admin(deps: Deps, chat: Chat, user_id: int | None) -> bool:
    if user_id is None:
        return False
    return await deps.admin.is_admin(chat.id, user_id, private=chat.type == "private")


async def _guard_callback(deps: Deps, callback: CallbackQuery) -> tuple[Message, str | None] | None:
    """Return the message and chat language for an allowed admin tap, else answer and stop."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(deps.i18n.t(None, "button-expired"), show_alert=True)
        return None
    lang = await _chat_language(deps, message.chat.id)
    if not await _is_admin(deps, message.chat, callback.from_user.id):
        await callback.answer(deps.i18n.t(lang, "not-admin"), show_alert=True)
        return None
    return message, lang


# --- onboarding --------------------------------------------------------------------------


async def on_start(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    user_id = message.from_user.id if message.from_user else None
    if not await _is_admin(deps, message.chat, user_id):
        await message.answer(deps.i18n.t(chat.language, "setup-admin-needed"))
        return
    await message.answer(
        deps.i18n.t(None, "pick-language"), reply_markup=keyboards.language_keyboard()
    )


async def on_language_chosen(callback: CallbackQuery, deps: Deps) -> None:
    guarded = await _guard_callback(deps, callback)
    if guarded is None:
        return
    message, lang = guarded
    code = (callback.data or "")[len(keyboards.LANG_PREFIX) :]
    if code not in SUPPORTED_LANGUAGES:
        await callback.answer(deps.i18n.t(lang, "button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.upsert_chat(
            session, message.chat.id, _CHAT_TYPES.get(message.chat.type, "group")
        )
        await repos.set_language(session, message.chat.id, code)
    intro = deps.i18n.t(code, "onboarding-intro")
    pick_zone = deps.i18n.t(code, "onboarding-pick-timezone")
    text = f"{intro}\n\n{pick_zone}"
    await message.edit_text(text, reply_markup=keyboards.timezone_keyboard(tzs.popular_zones(code)))
    await callback.answer()


async def on_zone_chosen(callback: CallbackQuery, deps: Deps) -> None:
    guarded = await _guard_callback(deps, callback)
    if guarded is None:
        return
    message, lang = guarded
    zone = (callback.data or "")[len(keyboards.TZ_PREFIX) :]
    if not tzs.is_valid_zone(zone):
        await callback.answer(deps.i18n.t(lang, "timezone-invalid-button"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_time_zone(session, message.chat.id, zone)
        if lang is not None:
            await repos.set_status(session, message.chat.id, "active")
    if lang is None:
        await message.edit_text(
            deps.i18n.t(None, "timezone-set", zone=zone, time=tzs.local_time_text(zone))
        )
    else:
        await message.edit_text(
            deps.i18n.t(lang, "setup-done", language=LANGUAGE_NAMES[lang], zone=zone)
        )
    await callback.answer()


# --- time zone and settings --------------------------------------------------------------


async def on_timezone(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    user_id = message.from_user.id if message.from_user else None
    if not await _is_admin(deps, message.chat, user_id):
        await message.answer(deps.i18n.t(chat.language, "not-admin"))
        return
    query = (command.args or "").strip()
    if not query:
        await message.answer(
            deps.i18n.t(chat.language, "onboarding-pick-timezone"),
            reply_markup=keyboards.timezone_keyboard(tzs.popular_zones(chat.language)),
        )
        return
    result = tzs.resolve(query)
    if result.kind == "exact":
        zone = result.zones[0]
        async with deps.sessions() as session, session.begin():
            await repos.set_time_zone(session, chat.chat_id, zone)
        await message.answer(
            deps.i18n.t(chat.language, "timezone-set", zone=zone, time=tzs.local_time_text(zone))
        )
    elif result.kind == "choices":
        await message.answer(
            deps.i18n.t(chat.language, "timezone-choose", query=query[: tzs.MAX_QUERY_LENGTH]),
            reply_markup=keyboards.timezone_keyboard(result.zones),
        )
    else:
        await message.answer(
            deps.i18n.t(chat.language, "timezone-not-found", query=query[: tzs.MAX_QUERY_LENGTH])
        )


async def on_settings(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    async with deps.sessions() as session:
        count = await repos.count_handles(session, chat.chat_id, PLATFORM)
    lang = chat.language
    text = deps.i18n.t(
        lang,
        "settings-summary",
        language=LANGUAGE_NAMES.get(lang or "", "-"),
        zone=chat.time_zone or deps.i18n.t(lang, "settings-timezone-unset"),
        count=count,
    )
    await message.answer(text, reply_markup=keyboards.settings_keyboard(deps.i18n, lang))


async def _show_menu(callback: CallbackQuery, deps: Deps, *, language_menu: bool) -> None:
    guarded = await _guard_callback(deps, callback)
    if guarded is None:
        return
    message, lang = guarded
    markup: InlineKeyboardMarkup
    if language_menu:
        text, markup = deps.i18n.t(None, "pick-language"), keyboards.language_keyboard()
    else:
        text = deps.i18n.t(lang, "onboarding-pick-timezone")
        markup = keyboards.timezone_keyboard(tzs.popular_zones(lang))
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def on_menu_language(callback: CallbackQuery, deps: Deps) -> None:
    await _show_menu(callback, deps, language_menu=True)


async def on_menu_timezone(callback: CallbackQuery, deps: Deps) -> None:
    await _show_menu(callback, deps, language_menu=False)


# --- watch list --------------------------------------------------------------------------


async def on_track(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is None:
        return
    t = deps.i18n.t
    lang = chat.language
    verb, _, rest = (command.args or "").strip().partition(" ")
    verb = verb.lower()
    if verb == "list":
        handles = await deps.watchlist.list(chat.chat_id)
        if not handles:
            await message.answer(t(lang, "track-list-empty"))
        else:
            header = t(lang, "track-list-header", count=len(handles))
            await message.answer(f"{header}\n{', '.join(handles)}")
        return
    if verb not in {"add", "remove"}:
        await message.answer(t(lang, "track-usage"))
        return
    user_id = message.from_user.id if message.from_user else None
    if not await _is_admin(deps, message.chat, user_id):
        await message.answer(t(lang, "not-admin"))
        return
    if not rest.strip():
        await message.answer(t(lang, "track-nothing"))
        return
    try:
        if verb == "add":
            lines = await _add(deps, chat, rest)
        else:
            lines = await _remove(deps, chat, rest)
    except SourceError:
        log.warning("track_source_error", exc_info=True)
        await message.answer(t(lang, "track-source-error"))
        return
    await message.answer("\n".join(lines) if lines else t(lang, "track-nothing"))


async def _add(deps: Deps, chat: repos.ChatRecord, text: str) -> list[str]:
    result = await deps.watchlist.add(chat.chat_id, text)
    t, lang = deps.i18n.t, chat.language
    lines: list[str] = []
    if result.added:
        lines.append(t(lang, "track-added", handles=", ".join(result.added)))
    if result.already:
        lines.append(t(lang, "track-already", handles=", ".join(result.already)))
    if result.unknown:
        lines.append(t(lang, "track-unknown", handles=", ".join(result.unknown)))
    if result.invalid:
        lines.append(t(lang, "track-invalid", handles=", ".join(result.invalid)))
    if result.over_limit:
        lines.append(
            t(lang, "track-limit", limit=deps.watchlist.limit, handles=", ".join(result.over_limit))
        )
    if result.truncated:
        lines.append(t(lang, "track-truncated", limit=INPUT_CAP))
    return lines


async def _remove(deps: Deps, chat: repos.ChatRecord, text: str) -> list[str]:
    result = await deps.watchlist.remove(chat.chat_id, text)
    t, lang = deps.i18n.t, chat.language
    lines: list[str] = []
    if result.removed:
        lines.append(t(lang, "track-removed", handles=", ".join(result.removed)))
    if result.not_found:
        lines.append(t(lang, "track-not-found", handles=", ".join(result.not_found)))
    return lines


# --- help and commands that are not built yet --------------------------------------------


async def on_help(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is not None:
        await message.answer(deps.i18n.t(chat.language, "help-text"))


async def on_coming_soon(message: Message, deps: Deps) -> None:
    chat = await _ensure_chat(deps, message.chat)
    if chat is not None:
        await message.answer(deps.i18n.t(chat.language, "coming-soon"))


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
            await event.answer(deps.i18n.t(record.language, "group-added"))
    elif new_status in _GONE:
        async with deps.sessions() as session, session.begin():
            await repos.set_status(session, chat.id, "removed")
        deps.admin.invalidate_chat(chat.id)


async def on_chat_member(event: ChatMemberUpdated, deps: Deps) -> None:
    deps.admin.invalidate(event.chat.id, event.new_chat_member.user.id)


def create_router() -> Router:
    """Build a fresh router; one per dispatcher so tests can build several."""
    router = Router(name="main")
    router.message.register(on_start, Command("start"))
    router.callback_query.register(on_language_chosen, F.data.startswith(keyboards.LANG_PREFIX))
    router.callback_query.register(on_zone_chosen, F.data.startswith(keyboards.TZ_PREFIX))
    router.message.register(on_timezone, Command("timezone"))
    router.message.register(on_settings, Command("settings"))
    router.callback_query.register(on_menu_language, F.data == keyboards.MENU_LANG)
    router.callback_query.register(on_menu_timezone, F.data == keyboards.MENU_TZ)
    router.message.register(on_track, Command("track", "friends"))
    router.message.register(on_help, Command("help"))
    router.message.register(on_coming_soon, Command(*_PLANNED_COMMANDS))
    router.my_chat_member.register(on_my_chat_member)
    router.chat_member.register(on_chat_member)
    return router
