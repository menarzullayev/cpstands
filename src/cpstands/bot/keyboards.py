"""Inline keyboards; callback data follows ``<area>:<action>[:<arg>]`` and stays under 64 bytes."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from cpstands.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, I18n

MAX_CALLBACK_BYTES = 64

LANG_PREFIX = "set:lang:"
TZ_PREFIX = "tz:set:"
MENU_LANG = "set:menu:lang"
MENU_TZ = "set:menu:tz"


def _button(text: str, data: str) -> InlineKeyboardButton:
    if len(data.encode()) > MAX_CALLBACK_BYTES:
        raise ValueError(f"callback data longer than {MAX_CALLBACK_BYTES} bytes: {data!r}")
    return InlineKeyboardButton(text=text, callback_data=data)


def language_keyboard() -> InlineKeyboardMarkup:
    row = [_button(LANGUAGE_NAMES[code], f"{LANG_PREFIX}{code}") for code in SUPPORTED_LANGUAGES]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def timezone_keyboard(zones: Sequence[str]) -> InlineKeyboardMarkup:
    buttons = [_button(zone, f"{TZ_PREFIX}{zone}") for zone in zones]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(i18n: I18n, lang: str | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(i18n.t(lang, "button-language"), MENU_LANG),
                _button(i18n.t(lang, "button-timezone"), MENU_TZ),
            ]
        ]
    )
