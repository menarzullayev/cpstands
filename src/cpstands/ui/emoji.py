# ruff: noqa: RUF001
"""Turn ordinary emoji in catalog text into Telegram custom emoji.

Catalogs keep plain emoji so translators never touch ids. When custom emoji are enabled the
bot rewrites each known emoji to ``<tg-emoji emoji-id="...">`` just before sending (Bot API 9.4:
the bot owner needs Telegram Premium). An emoji without a custom twin stays as it is.
"""

from __future__ import annotations

import re

from cpstands.ui.emoji_ids import CUSTOM_EMOJI_IDS

VS16 = chr(0xFE0F)  # variation selector-16, appended to some emoji

# The RestrictedEmoji set has no twin for these, so each is drawn with the closest emoji it has.
# The tag's text is the twin, not the plain character: Telegram refuses a custom emoji whose text
# is not that emoji (``→`` gave ENTITY_TEXT_INVALID on 2026-11-08).
ALIASES: dict[str, str] = {
    "⚠️": "❗",
    "ℹ️": "❕",
    "🔒": "🔐",
    "🕐": "⏳",
    "⏱": "⌛",
    "🗑": "🧽",
    "🧹": "🧽",
    "⚙️": "🗂",
    "🛠": "💻",
    "📟": "📱",
    "⏸": "🔕",
    "▶️": "🔔",
    "🔁": "🔄",
    "◀": "👈",
    "▶": "👉",
    "⏮": "🔝",
    "⏭": "🏁",
    "→": "👉",
    "⬜": "❌",
    "▫️": "➖",
}
_IDS: dict[str, str] = {
    **CUSTOM_EMOJI_IDS,
    **{plain: CUSTOM_EMOJI_IDS[twin] for plain, twin in ALIASES.items()},
}

# Longest first so a sequence with a variation selector wins over its bare base.
_PATTERN = re.compile("|".join(re.escape(e) for e in sorted(_IDS, key=len, reverse=True)))


def custom_emoji_id(emoji: str) -> str | None:
    return _IDS.get(emoji) or _IDS.get(emoji.replace(VS16, ""))


# An emoji that is already wrapped (a translated piece placed inside another message) is kept.
_WRAPPED = r"<tg-emoji\s[^>]*>.*?</tg-emoji>"
_DECORATE = re.compile(f"({_WRAPPED})|{_PATTERN.pattern}", re.DOTALL)


def decorate(html_text: str) -> str:
    """Wrap every known emoji of an HTML message in a ``tg-emoji`` tag; safe to run twice."""

    def wrap(m: re.Match[str]) -> str:
        if m.group(1) is not None:
            return m.group(1)
        emoji = m.group(0)
        text = ALIASES.get(emoji, emoji)
        return f'<tg-emoji emoji-id="{_IDS[emoji]}">{text}</tg-emoji>'

    return _DECORATE.sub(wrap, html_text)
