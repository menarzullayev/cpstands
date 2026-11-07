from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cpstands.services import timezone as tz


@pytest.mark.parametrize(
    ("query", "zone"),
    [
        ("Tashkent", "Asia/Tashkent"),
        ("toshkent", "Asia/Tashkent"),
        ("ТАШКЕНТ", "Asia/Tashkent"),
        ("  asia/tashkent ", "Asia/Tashkent"),
        ("Asia/Tashkent", "Asia/Tashkent"),
        ("America/New York", "America/New_York"),
        ("moskva", "Europe/Moscow"),
        ("Москва", "Europe/Moscow"),
        ("Tokyo", "Asia/Tokyo"),
        ("kiev", "Europe/Kyiv"),
        ("UTC", "UTC"),
    ],
)
def test_exact_matches_are_resolved_directly(query: str, zone: str) -> None:
    assert tz.resolve(query) == tz.Resolution("exact", (zone,))


def test_tashkent_is_never_karachi() -> None:
    # Regression for the geocoder that mapped Tashkent to Asia/Karachi.
    assert "Asia/Karachi" not in tz.resolve("tashkent").zones


def test_partial_input_offers_choices_instead_of_guessing() -> None:
    result = tz.resolve("new_y")
    assert result.kind == "choices"
    assert "America/New_York" in result.zones
    assert len(result.zones) <= tz.MAX_CHOICES


def test_ambiguous_city_name_offers_all_candidates() -> None:
    result = tz.resolve("london")
    assert result.kind in {"exact", "choices"}
    assert "Europe/London" in result.zones


@pytest.mark.parametrize("query", ["", "   ", "zz", "qwertyuiop12345", "a" * 65, "tash\x00kent"])
def test_garbage_is_rejected(query: str) -> None:
    assert tz.resolve(query).kind == "none"


def test_legacy_and_system_names_are_not_offered() -> None:
    zones = tz.known_zones()
    assert "Asia/Calcutta" not in zones
    assert "Europe/Kiev" not in zones
    assert not any(z.startswith(("Etc/", "US/", "SystemV/")) for z in zones)
    assert "Asia/Kolkata" in zones
    assert "UTC" in zones


def test_aliases_and_popular_lists_point_to_known_zones() -> None:
    zones = tz.known_zones()
    for alias, target in tz._ALIASES.items():
        assert target in zones, (alias, target)
    for language in ("uz", "ru", "en"):
        assert set(tz.popular_zones(language)) <= zones


def test_is_valid_zone_rejects_unknown_and_injection() -> None:
    assert tz.is_valid_zone("Asia/Tashkent")
    assert not tz.is_valid_zone("Asia/Nowhere")
    assert not tz.is_valid_zone("../../etc/passwd")
    assert not tz.is_valid_zone("")


def test_local_time_text_uses_the_zone_offset() -> None:
    noon_utc = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    assert tz.local_time_text("Asia/Tashkent", noon_utc) == "17:00"
    assert tz.local_time_text("UTC", noon_utc) == "12:00"
