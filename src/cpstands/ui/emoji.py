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
# The plain emoji stays as the tag's fallback text, so clients without custom emoji see no change.
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
}
_IDS: dict[str, str] = {
    **CUSTOM_EMOJI_IDS,
    **{plain: CUSTOM_EMOJI_IDS[twin] for plain, twin in ALIASES.items()},
}

# Longest first so a sequence with a variation selector wins over its bare base.
_PATTERN = re.compile("|".join(re.escape(e) for e in sorted(_IDS, key=len, reverse=True)))


def custom_emoji_id(emoji: str) -> str | None:
    return _IDS.get(emoji) or _IDS.get(emoji.replace(VS16, ""))


def decorate(html_text: str) -> str:
    """Wrap every known emoji of an HTML message in a ``tg-emoji`` tag."""
    return _PATTERN.sub(
        lambda m: f'<tg-emoji emoji-id="{_IDS[m.group(0)]}">{m.group(0)}</tg-emoji>',
        html_text,
    )
