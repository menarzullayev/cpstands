"""Turn ordinary emoji in catalog text into Telegram custom emoji.

Catalogs keep plain emoji so translators never touch ids. When custom emoji are enabled the
bot rewrites each known emoji to ``<tg-emoji emoji-id="...">`` just before sending (Bot API 9.4:
the bot owner needs Telegram Premium). An emoji without a custom twin stays as it is.
"""

from __future__ import annotations

import re

from cpstands.ui.emoji_ids import CUSTOM_EMOJI_IDS

VS16 = chr(0xFE0F)  # variation selector-16, appended to some emoji

# Longest first so a sequence with a variation selector wins over its bare base.
_PATTERN = re.compile(
    "|".join(re.escape(e) for e in sorted(CUSTOM_EMOJI_IDS, key=len, reverse=True))
)


def custom_emoji_id(emoji: str) -> str | None:
    return CUSTOM_EMOJI_IDS.get(emoji) or CUSTOM_EMOJI_IDS.get(emoji.replace(VS16, ""))


def decorate(html_text: str) -> str:
    """Wrap every known emoji of an HTML message in a ``tg-emoji`` tag."""
    return _PATTERN.sub(
        lambda m: f'<tg-emoji emoji-id="{CUSTOM_EMOJI_IDS[m.group(0)]}">{m.group(0)}</tg-emoji>',
        html_text,
    )
