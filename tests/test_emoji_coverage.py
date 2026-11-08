"""Every emoji the bot can show has a custom twin or a documented stand-in."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cpstands.bot.standings_view import PLAIN_CELL_EMOJI
from cpstands.ui.emoji import ALIASES, custom_emoji_id, decorate
from cpstands.ui.emoji_ids import CUSTOM_EMOJI_IDS

SRC = Path(__file__).resolve().parents[1] / "src" / "cpstands"
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐⭕⏩-⏺⌚-⌛][️]?")
# Plain symbols with no twin and no stand-in in the set, and the table cell marks that are plain
# on purpose (a message keeps at most 100 custom emoji).
TYPOGRAPHY = set("▪") | PLAIN_CELL_EMOJI


def _used() -> set[str]:
    found: set[str] = set()
    for path in [*SRC.rglob("*.py"), *SRC.rglob("*.ftl")]:
        if path.name == "emoji_ids.py":
            continue
        found.update(_EMOJI.findall(path.read_text(encoding="utf-8")))
    return found


def test_every_used_emoji_is_custom_or_listed_typography() -> None:
    uncovered = {
        e for e in _used() if custom_emoji_id(e) is None and e.replace("️", "") not in TYPOGRAPHY
    }
    assert not uncovered, f"no custom emoji for: {sorted(uncovered)}"


def test_aliases_point_at_real_ids() -> None:
    assert all(twin in CUSTOM_EMOJI_IDS for twin in ALIASES.values())


def test_a_stand_in_is_wrapped_with_its_twin_as_text() -> None:
    out = decorate("⚠️ careful")
    assert out.startswith('<tg-emoji emoji-id="')
    assert ">❗</tg-emoji>" in out


@pytest.mark.parametrize("symbol", ["▪", "·"])
def test_plain_typography_is_left_alone(symbol: str) -> None:
    assert decorate(symbol) == symbol
    assert custom_emoji_id(symbol) is None


def test_buttons_are_built_through_the_helpers_so_their_icons_can_be_custom() -> None:
    offenders = [
        path.name
        for path in (SRC / "bot").glob("*.py")
        if path.name != "keyboards.py" and "InlineKeyboardButton(" in path.read_text("utf-8")
    ]
    assert not offenders, f"build buttons with keyboards.button/link: {offenders}"


def test_pagination_and_toggle_buttons_carry_custom_icons() -> None:
    from cpstands.bot import rank_view

    def say(key: str) -> str:
        return key

    markup = rank_view.keyboard(60, 1, say, icons=True)  # type: ignore[arg-type]
    nav = markup.inline_keyboard[0]
    icons = [b.icon_custom_emoji_id for b in nav]
    assert icons[2] is None  # the page counter has no icon
    assert icons[1]
    assert icons[3]
    assert all(b.text.replace(" / ", "").isdigit() for b in nav)
    plain = rank_view.keyboard(60, 1, say, icons=False)  # type: ignore[arg-type]
    assert plain.inline_keyboard[0][1].text == "◀ 1"


def test_decorate_never_nests_tg_emoji() -> None:
    """A translated line with custom emoji, placed inside another message, is not wrapped again.

    Telegram refuses nested tg-emoji with ENTITY_TEXT_INVALID (seen on /rating, 2026-11-08).
    """
    from cpstands.ui.emoji import decorate

    once = decorate("🏆 1094 → 1141")
    assert decorate(once) == once
    assert re.search(r"<tg-emoji[^>]*>\s*<tg-emoji", decorate(once)) is None
    assert decorate(f"👤 <b>x</b>\n\n{once}").count("<tg-emoji") == 3


def test_every_tag_carries_the_emoji_its_id_belongs_to() -> None:
    """Telegram refuses a custom emoji whose text is another character (ENTITY_TEXT_INVALID)."""
    from cpstands.ui.emoji import ALIASES, decorate
    from cpstands.ui.emoji_ids import CUSTOM_EMOJI_IDS

    by_id = {v: k for k, v in CUSTOM_EMOJI_IDS.items()}
    sample = " ".join([*CUSTOM_EMOJI_IDS, *ALIASES])
    tags = re.findall(r'<tg-emoji emoji-id="(\d+)">(.*?)</tg-emoji>', decorate(sample))
    assert len(tags) == len(CUSTOM_EMOJI_IDS) + len(ALIASES)
    for emoji_id, text in tags:
        assert text == by_id[emoji_id], (emoji_id, text)
    assert "→</tg-emoji>" not in decorate("1141 → 1094")
