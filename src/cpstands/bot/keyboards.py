"""Inline keyboards; callback data follows ``<area>:<action>[:<arg>]`` and stays under 64 bytes.

Button colors use the Bot API 9.4 ``style`` field. Icons are normal emoji in the button text,
or custom-emoji icons when the bot is allowed to use them (``BUTTON_ICONS``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from cpstands.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, Translator
from cpstands.ui.emoji import custom_emoji_id

MAX_CALLBACK_BYTES = 64

LANG_PREFIX = "set:lang:"
TZ_PREFIX = "tz:set:"
TONE_PREFIX = "set:tone:"
MENU_LANG = "set:menu:lang"
MENU_TZ = "set:menu:tz"
HELP_SETTINGS = "help:settings"
HELP_TRACK = "help:track"

type Style = Literal["primary", "success", "danger"]


def button(
    text: str,
    data: str,
    *,
    emoji: str | None = None,
    style: Style | None = None,
    icons: bool = False,
) -> InlineKeyboardButton:
    if len(data.encode()) > MAX_CALLBACK_BYTES:
        raise ValueError(f"callback data longer than {MAX_CALLBACK_BYTES} bytes: {data!r}")
    icon = custom_emoji_id(emoji) if emoji and icons else None
    label = text if icon or not emoji else f"{emoji} {text}"
    return InlineKeyboardButton(
        text=label, callback_data=data, style=style, icon_custom_emoji_id=icon
    )


def link(
    text: str,
    url: str,
    *,
    emoji: str | None = None,
    style: Style | None = None,
    icons: bool = False,
) -> InlineKeyboardButton:
    icon = custom_emoji_id(emoji) if emoji and icons else None
    label = text if icon or not emoji else f"{emoji} {text}"
    return InlineKeyboardButton(text=label, url=url, style=style, icon_custom_emoji_id=icon)


def language_keyboard(current: str | None = None, *, icons: bool = False) -> InlineKeyboardMarkup:
    row = [
        button(
            LANGUAGE_NAMES[code],
            f"{LANG_PREFIX}{code}",
            style="primary" if code == current else None,
            icons=icons,
        )
        for code in SUPPORTED_LANGUAGES
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def timezone_keyboard(
    zones: Sequence[str], current: str | None = None, *, icons: bool = False
) -> InlineKeyboardMarkup:
    buttons = [
        button(
            zone, f"{TZ_PREFIX}{zone}", style="primary" if zone == current else None, icons=icons
        )
        for zone in zones
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def help_keyboard(say: Translator, *, icons: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    say("button-help-settings"),
                    HELP_SETTINGS,
                    emoji="⚙️",
                    style="primary",
                    icons=icons,
                ),
                button(say("button-help-track"), HELP_TRACK, emoji="👥", icons=icons),
            ]
        ]
    )
