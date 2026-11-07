"""Offline time-zone resolution: a typed city or zone name becomes a confirmed IANA name.

No geocoding service is used on purpose: the one tried during design mapped "Tashkent" to
Asia/Karachi. A zone is stored only after an exact match or after the user taps a button.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, available_timezones

MAX_QUERY_LENGTH = 64
MAX_CHOICES = 8

_EXCLUDED_PREFIXES = (
    "Etc/",
    "SystemV/",
    "US/",
    "Canada/",
    "Brazil/",
    "Chile/",
    "Mexico/",
    "posix/",
    "right/",
)
# Legacy names that tzdata still ships next to their modern replacement.
_LEGACY = frozenset(
    {
        "Asia/Calcutta",
        "Asia/Katmandu",
        "Asia/Saigon",
        "Asia/Rangoon",
        "Asia/Ulan_Bator",
        "Asia/Thimbu",
        "Asia/Dacca",
        "Asia/Macao",
        "Asia/Ujung_Pandang",
        "Atlantic/Faeroe",
        "Europe/Kiev",
        "Europe/Uzhgorod",
        "Europe/Zaporozhye",
        "America/Buenos_Aires",
        "America/Indianapolis",
        "Pacific/Truk",
        "Pacific/Ponape",
    }
)

# Normalized query -> IANA name. Covers Uzbek/Russian spellings and the cities our users type.
_ALIASES: dict[str, str] = {
    "toshkent": "Asia/Tashkent",
    "tashkent": "Asia/Tashkent",
    "ташкент": "Asia/Tashkent",
    "uzbekistan": "Asia/Tashkent",
    "ozbekiston": "Asia/Tashkent",
    "o'zbekiston": "Asia/Tashkent",
    "узбекистан": "Asia/Tashkent",
    "samarqand": "Asia/Samarkand",
    "samarkand": "Asia/Samarkand",
    "самарканд": "Asia/Samarkand",
    "moskva": "Europe/Moscow",
    "moscow": "Europe/Moscow",
    "москва": "Europe/Moscow",
    "almaty": "Asia/Almaty",
    "алматы": "Asia/Almaty",
    "bishkek": "Asia/Bishkek",
    "бишкек": "Asia/Bishkek",
    "dushanbe": "Asia/Dushanbe",
    "душанбе": "Asia/Dushanbe",
    "ashgabat": "Asia/Ashgabat",
    "ашхабад": "Asia/Ashgabat",
    "baku": "Asia/Baku",
    "баку": "Asia/Baku",
    "kyiv": "Europe/Kyiv",
    "kiev": "Europe/Kyiv",
    "киев": "Europe/Kyiv",
    "minsk": "Europe/Minsk",
    "минск": "Europe/Minsk",
    "istanbul": "Europe/Istanbul",
    "стамбул": "Europe/Istanbul",
    "delhi": "Asia/Kolkata",
    "new delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "seoul": "Asia/Seoul",
    "utc": "UTC",
    "gmt": "UTC",
}

_POPULAR: dict[str, tuple[str, ...]] = {
    "uz": (
        "Asia/Tashkent",
        "Asia/Almaty",
        "Asia/Bishkek",
        "Asia/Dushanbe",
        "Europe/Moscow",
        "Europe/Istanbul",
    ),
    "ru": (
        "Europe/Moscow",
        "Asia/Tashkent",
        "Asia/Almaty",
        "Europe/Kyiv",
        "Europe/Minsk",
        "Asia/Baku",
    ),
    "en": (
        "UTC",
        "Europe/London",
        "America/New_York",
        "Europe/Berlin",
        "Asia/Tashkent",
        "Asia/Kolkata",
    ),
}

_SEPARATORS = re.compile(r"[\s_]+")
# Right/left single quotation marks, modifier letter turned comma, grave accent.
_APOSTROPHES = ("’", "‘", "ʻ", "`")  # noqa: RUF001


@dataclass(frozen=True, slots=True)
class Resolution:
    """Outcome of a lookup: ``exact`` is stored at once, ``choices`` need a button tap."""

    kind: Literal["exact", "choices", "none"]
    zones: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def known_zones() -> frozenset[str]:
    """Zones the bot accepts: current IANA names without legacy aliases."""
    names = set()
    for name in available_timezones():
        if name in _LEGACY or name.startswith(_EXCLUDED_PREFIXES):
            continue
        if "/" not in name and name != "UTC":
            continue
        names.add(name)
    return frozenset(names)


def is_valid_zone(name: str) -> bool:
    return name in known_zones()


def normalize(text: str) -> str:
    """Lowercase, unify apostrophes, drop accents and collapse separators."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    for variant in _APOSTROPHES:
        folded = folded.replace(variant, "'")
    return _SEPARATORS.sub(" ", folded).strip()


def _flat(name: str) -> str:
    return normalize(name)


def resolve(query: str) -> Resolution:
    """Map free text to zones; never guesses silently."""
    cleaned = query.strip()
    if (
        not cleaned
        or len(cleaned) > MAX_QUERY_LENGTH
        or any(unicodedata.category(ch).startswith("C") for ch in cleaned)
    ):
        return Resolution("none")
    key = normalize(cleaned)
    zones = known_zones()

    by_flat = {_flat(name): name for name in zones}
    if key in by_flat:
        return Resolution("exact", (by_flat[key],))
    alias = _ALIASES.get(key)
    if alias is not None and alias in zones:
        return Resolution("exact", (alias,))

    cities: dict[str, list[str]] = {}
    for name in zones:
        cities.setdefault(_flat(name.rsplit("/", 1)[-1]), []).append(name)
    same_city = sorted(cities.get(key, []))
    if len(same_city) == 1:
        return Resolution("exact", (same_city[0],))
    if len(same_city) > 1:
        return Resolution("choices", tuple(same_city[:MAX_CHOICES]))

    starts = sorted(n for n in zones if _flat(n.rsplit("/", 1)[-1]).startswith(key))
    contains = sorted(n for n in zones if key in _flat(n) and n not in starts)
    found = (starts + contains)[:MAX_CHOICES]
    if len(key) >= 3 and found:
        return Resolution("choices", tuple(found))
    return Resolution("none")


def popular_zones(language: str | None) -> tuple[str, ...]:
    return _POPULAR.get(language or "", _POPULAR["en"])


def local_time_text(zone: str, now: datetime | None = None) -> str:
    """Wall-clock time in ``zone`` as HH:MM, shown so the user can spot a wrong zone."""
    moment = now or datetime.now(UTC)
    return moment.astimezone(ZoneInfo(zone)).strftime("%H:%M")
