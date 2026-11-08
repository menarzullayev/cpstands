"""``/settings``: one hub and its submenus (reminders, alert level, friends, table, summary)."""

from __future__ import annotations

import re

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from cpstands.bot import keyboards
from cpstands.bot.common import (
    DEFAULT_REMINDER_OFFSETS,
    ensure_chat,
    refresh,
    say,
    tap_context,
)
from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.i18n import LANGUAGE_NAMES, TONES, Translator
from cpstands.services import timezone as tzs
from cpstands.services.watchlist import PLATFORM

log = structlog.get_logger(__name__)

REMINDER_CHOICES = (
    4320,
    1440,
    120,
    60,
    10,
)  # minutes before the start: 3 d, 24 h, 2 h, 1 h, 10 min
COLUMN_CHOICES = (8, 12, 16)
FRIENDS_PER_PAGE = 8
LEVELS = (0, 1, 2, 3, 4)

MENU_MAIN = "set:menu:main"
MENU_REM = "set:menu:rem"
MENU_ALR = "set:menu:alr"
RT_PREFIX = "set:rt:"
LVL_PREFIX = "set:lvl:"
COLS_PREFIX = "set:cols:"
SUM_PREFIX = "set:sum:"
FR_LIST = "fr:l:"
FR_DETAIL = "fr:d:"
FR_TOGGLE = "fr:t:"

_KEY_RE = re.compile(r"^[a-z0-9_.-]{1,24}$")


def offset_label(minutes: int) -> str:
    """Language-neutral short label: ``3d``, ``24h``, ``2h``, ``10m``."""
    if minutes % 1440 == 0 and minutes >= 2880:
        return f"{minutes // 1440}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


def reminders_text(deps: Deps, chat: repos.ChatRecord) -> str:
    if not chat.reminder_offsets:
        return say(deps, chat)("word-off")
    return " · ".join(offset_label(m) for m in chat.reminder_offsets)


# --- the hub ----------------------------------------------------------------------------


async def settings_view(deps: Deps, chat: repos.ChatRecord) -> tuple[str, InlineKeyboardMarkup]:
    async with deps.sessions() as session:
        count = await repos.count_handles(session, chat.chat_id, PLATFORM)
    tr = say(deps, chat)
    text = tr(
        "settings-summary",
        language=LANGUAGE_NAMES.get(chat.language or "", "-"),
        zone=chat.time_zone or tr("settings-timezone-unset"),
        mood=chat.tone,
        reminders=reminders_text(deps, chat),
        level=chat.notify_level,
        cols=chat.table_cols,
        summary="on" if chat.summary_enabled else "off",
        count=count,
    )
    return text, _hub_keyboard(deps, chat, tr)


def _hub_keyboard(deps: Deps, chat: repos.ChatRecord, tr: Translator) -> InlineKeyboardMarkup:
    icons = deps.icons
    other_tone = "neutral" if chat.tone == "playful" else "playful"
    next_cols = COLUMN_CHOICES[(COLUMN_CHOICES.index(chat.table_cols) + 1) % len(COLUMN_CHOICES)]
    next_summary = "off" if chat.summary_enabled else "on"
    state = "on" if chat.summary_enabled else "off"
    b = keyboards.button
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                b(tr("button-language"), keyboards.MENU_LANG, emoji="🌍", icons=icons),
                b(tr("button-timezone"), keyboards.MENU_TZ, emoji="🧭", icons=icons),
            ],
            [
                b(
                    tr("button-tone", mood=chat.tone),
                    f"{keyboards.TONE_PREFIX}{other_tone}",
                    emoji="🎭",
                    icons=icons,
                ),
                b(tr("button-reminders-menu"), MENU_REM, emoji="🔔", icons=icons),
            ],
            [
                b(tr("button-alerts-menu"), MENU_ALR, emoji="🔥", icons=icons),
                b(
                    tr("button-columns", n=chat.table_cols),
                    f"{COLS_PREFIX}{next_cols}",
                    emoji="📊",
                    icons=icons,
                ),
            ],
            [
                b(
                    tr("button-summary", state=state),
                    f"{SUM_PREFIX}{next_summary}",
                    emoji="🏁",
                    icons=icons,
                ),
                b(tr("button-friends"), f"{FR_LIST}0", emoji="👥", icons=icons),
            ],
        ]
    )


async def on_settings(message: Message, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    text, markup = await settings_view(deps, chat)
    await message.answer(text, reply_markup=markup)


async def _show_hub(callback: CallbackQuery, deps: Deps, message: Message, chat_id: int) -> None:
    text, markup = await settings_view(deps, await refresh(deps, chat_id))
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def on_menu_main(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await _show_hub(callback, deps, message, chat.chat_id)


async def on_menu_language(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await message.edit_text(
        deps.i18n.t(None, "pick-language"),
        reply_markup=keyboards.language_keyboard(chat.language, icons=deps.icons),
    )
    await callback.answer()


async def on_menu_timezone(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await message.edit_text(
        say(deps, chat)("onboarding-pick-timezone"),
        reply_markup=keyboards.timezone_keyboard(
            tzs.popular_zones(chat.language), chat.time_zone, icons=deps.icons
        ),
    )
    await callback.answer()


async def on_tone_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    tone = (callback.data or "")[len(keyboards.TONE_PREFIX) :]
    if tone not in TONES:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_tone(session, chat.chat_id, tone)
    await _show_hub(callback, deps, message, chat.chat_id)


# --- reminders --------------------------------------------------------------------------


def _reminders_keyboard(deps: Deps, chat: repos.ChatRecord) -> InlineKeyboardMarkup:
    tr = say(deps, chat)
    chosen = set(chat.reminder_offsets)
    buttons = [
        keyboards.button(
            offset_label(m),
            f"{RT_PREFIX}{m}",
            emoji="✅" if m in chosen else "⬜",
            icons=deps.icons,
        )
        for m in REMINDER_CHOICES
    ]
    back = keyboards.button(tr("button-back"), MENU_MAIN, emoji="◀", icons=deps.icons)
    return InlineKeyboardMarkup(inline_keyboard=[buttons, [back]])


async def _show_reminders(
    callback: CallbackQuery, deps: Deps, message: Message, chat_id: int
) -> None:
    chat = await refresh(deps, chat_id)
    await message.edit_text(
        say(deps, chat)("reminders-menu"), reply_markup=_reminders_keyboard(deps, chat)
    )
    await callback.answer()


async def on_menu_reminders(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await _show_reminders(callback, deps, message, chat.chat_id)


async def on_reminder_toggle(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    raw = (callback.data or "")[len(RT_PREFIX) :]
    if not raw.isdigit() or int(raw) not in REMINDER_CHOICES:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    minutes = int(raw)
    chosen = set(chat.reminder_offsets) ^ {minutes}
    async with deps.sessions() as session, session.begin():
        await repos.set_reminder_offsets(session, chat.chat_id, sorted(chosen, reverse=True))
    if chosen:
        await deps.contests.plan()
    await _show_reminders(callback, deps, message, chat.chat_id)


# --- alert level ------------------------------------------------------------------------


def _alerts_keyboard(deps: Deps, chat: repos.ChatRecord) -> InlineKeyboardMarkup:
    tr = say(deps, chat)
    rows = [
        [
            keyboards.button(
                tr("button-level", level=level),
                f"{LVL_PREFIX}{level}",
                style="primary" if level == chat.notify_level else None,
            )
        ]
        for level in LEVELS
    ]
    rows.append([keyboards.button(tr("button-back"), MENU_MAIN, emoji="◀", icons=deps.icons)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def on_menu_alerts(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    await message.edit_text(
        say(deps, chat)("alerts-menu"), reply_markup=_alerts_keyboard(deps, chat)
    )
    await callback.answer()


async def on_level_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    raw = (callback.data or "")[len(LVL_PREFIX) :]
    if not raw.isdigit() or int(raw) not in LEVELS:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_notify_level(session, chat.chat_id, int(raw))
    await _show_hub(callback, deps, message, chat.chat_id)


# --- table width and summary ------------------------------------------------------------


async def on_cols_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    raw = (callback.data or "")[len(COLS_PREFIX) :]
    if not raw.isdigit() or int(raw) not in COLUMN_CHOICES:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_table_cols(session, chat.chat_id, int(raw))
    await _show_hub(callback, deps, message, chat.chat_id)


async def on_summary_chosen(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    value = (callback.data or "")[len(SUM_PREFIX) :]
    if value not in {"on", "off"}:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    async with deps.sessions() as session, session.begin():
        await repos.set_summary_enabled(session, chat.chat_id, value == "on")
    await _show_hub(callback, deps, message, chat.chat_id)


# --- friends ----------------------------------------------------------------------------


def friend_pages(total: int) -> int:
    return max(1, -(-total // FRIENDS_PER_PAGE))


async def _friends_view(
    deps: Deps, chat: repos.ChatRecord, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    async with deps.sessions() as session:
        friends = await repos.list_friends(session, chat.chat_id, PLATFORM)
    tr = say(deps, chat)
    back = keyboards.button(tr("button-back"), MENU_MAIN, emoji="◀", icons=deps.icons)
    if not friends:
        return tr("friends-empty"), InlineKeyboardMarkup(inline_keyboard=[[back]])
    pages = friend_pages(len(friends))
    page = min(max(page, 0), pages - 1)
    shown = friends[page * FRIENDS_PER_PAGE : (page + 1) * FRIENDS_PER_PAGE]
    rows = []
    for friend in shown:
        muted = not (friend.notify_solve or friend.notify_systest or friend.notify_upsolve)
        mark = "🔕 " if muted else ""
        rows.append(
            [keyboards.button(f"{mark}{friend.display}", f"{FR_DETAIL}{page}:{friend.key}")]
        )
    if pages > 1:
        rows.append(
            [
                keyboards.button("◀", f"{FR_LIST}{max(page - 1, 0)}"),
                keyboards.button(f"{page + 1} / {pages}", "st:noop"),
                keyboards.button("▶", f"{FR_LIST}{min(page + 1, pages - 1)}"),
            ]
        )
    rows.append([back])
    return tr("friends-menu", count=len(friends)), InlineKeyboardMarkup(inline_keyboard=rows)


async def on_friends_list(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    raw = (callback.data or "")[len(FR_LIST) :]
    if not raw.isdigit():
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    text, markup = await _friends_view(deps, chat, int(raw))
    await message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def _detail_view(
    deps: Deps, chat: repos.ChatRecord, page: int, key: str
) -> tuple[str, InlineKeyboardMarkup] | None:
    async with deps.sessions() as session:
        friend = await repos.get_friend(session, chat.chat_id, PLATFORM, key)
    if friend is None:
        return None
    tr = say(deps, chat)
    labels = (
        tr("button-toggle-show"),
        tr("button-toggle-solve"),
        tr("button-toggle-systest"),
        tr("button-toggle-upsolve"),
    )
    rows = []
    for index, field in enumerate(repos.TOGGLE_FIELDS):
        on = friend.toggle(field)
        rows.append(
            [
                keyboards.button(
                    labels[index],
                    f"{FR_TOGGLE}{page}:{index}:{key}",
                    emoji="✅" if on else "⬜",
                    icons=deps.icons,
                )
            ]
        )
    rows.append(
        [keyboards.button(tr("button-back"), f"{FR_LIST}{page}", emoji="◀", icons=deps.icons)]
    )
    return tr("friend-detail", handle=friend.display), InlineKeyboardMarkup(inline_keyboard=rows)


def _parse_friend(data: str, prefix: str, *, toggle: bool) -> tuple[int, int, str] | None:
    parts = data[len(prefix) :].split(":")
    try:
        if toggle:
            page, index, key = int(parts[0]), int(parts[1]), parts[2]
        else:
            page, index, key = int(parts[0]), 0, parts[1]
    except (IndexError, ValueError):
        return None
    if page < 0 or not 0 <= index < len(repos.TOGGLE_FIELDS) or not _KEY_RE.match(key):
        return None
    return page, index, key


async def on_friend_detail(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    parsed = _parse_friend(callback.data or "", FR_DETAIL, toggle=False)
    view = await _detail_view(deps, chat, parsed[0], parsed[2]) if parsed else None
    if view is None:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    await message.edit_text(view[0], reply_markup=view[1])
    await callback.answer()


async def on_friend_toggle(callback: CallbackQuery, deps: Deps) -> None:
    context = await tap_context(deps, callback, admin=True)
    if context is None:
        return
    message, chat = context
    parsed = _parse_friend(callback.data or "", FR_TOGGLE, toggle=True)
    if parsed is None:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    page, index, key = parsed
    field = repos.TOGGLE_FIELDS[index]
    async with deps.sessions() as session, session.begin():
        friend = await repos.get_friend(session, chat.chat_id, PLATFORM, key)
        if friend is not None:
            await repos.set_friend_toggle(
                session, chat.chat_id, PLATFORM, key, field, not friend.toggle(field)
            )
    view = await _detail_view(deps, chat, page, key)
    if view is None:
        await callback.answer(say(deps, chat)("button-expired"), show_alert=True)
        return
    await message.edit_text(view[0], reply_markup=view[1])
    await callback.answer()


def create_settings_router() -> Router:
    router = Router(name="settings")
    router.message.register(on_settings, Command("settings"))
    router.callback_query.register(on_menu_main, F.data == MENU_MAIN)
    router.callback_query.register(on_menu_language, F.data == keyboards.MENU_LANG)
    router.callback_query.register(on_menu_timezone, F.data == keyboards.MENU_TZ)
    router.callback_query.register(on_tone_chosen, F.data.startswith(keyboards.TONE_PREFIX))
    router.callback_query.register(on_menu_reminders, F.data == MENU_REM)
    router.callback_query.register(on_reminder_toggle, F.data.startswith(RT_PREFIX))
    router.callback_query.register(on_menu_alerts, F.data == MENU_ALR)
    router.callback_query.register(on_level_chosen, F.data.startswith(LVL_PREFIX))
    router.callback_query.register(on_cols_chosen, F.data.startswith(COLS_PREFIX))
    router.callback_query.register(on_summary_chosen, F.data.startswith(SUM_PREFIX))
    router.callback_query.register(on_friends_list, F.data.startswith(FR_LIST))
    router.callback_query.register(on_friend_detail, F.data.startswith(FR_DETAIL))
    router.callback_query.register(on_friend_toggle, F.data.startswith(FR_TOGGLE))
    return router


__all__ = ["DEFAULT_REMINDER_OFFSETS", "create_settings_router", "settings_view"]
