"""Every emoji the bot can show has a custom twin or a documented stand-in."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cpstands.ui.emoji import ALIASES, custom_emoji_id, decorate
from cpstands.ui.emoji_ids import CUSTOM_EMOJI_IDS

SRC = Path(__file__).resolve().parents[1] / "src" / "cpstands"
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐⭕⏩-⏺⌚-⌛][️]?")
# Plain symbols the Codeforces-style navigation uses; the set has no twin for them.
TYPOGRAPHY = set("◀▶⏮⏭→⬜▫️▪")


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


def test_a_stand_in_is_wrapped_and_keeps_its_fallback_text() -> None:
    out = decorate("⚠️ careful")
    assert out.startswith('<tg-emoji emoji-id="')
    assert ">⚠️</tg-emoji>" in out


@pytest.mark.parametrize("symbol", ["◀", "→"])
def test_plain_typography_is_left_alone(symbol: str) -> None:
    assert decorate(symbol) == symbol
    assert custom_emoji_id(symbol) is None
