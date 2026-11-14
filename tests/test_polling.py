from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cpstands.domain.contest import FetchMeta
from cpstands.sources.polling import next_fetch_time

NOW = datetime(2026, 11, 8, 12, 0, 0, tzinfo=UTC)


def meta(expires_at: datetime | None) -> FetchMeta:
    return FetchMeta(
        fetched_at=NOW,
        duration_s=0.5,
        wire_bytes=100,
        decoded_bytes=1000,
        expires_at=expires_at,
        cache_status="HIT",
    )


def test_future_expiry_schedules_just_after_it() -> None:
    expires = NOW + timedelta(seconds=40)
    assert next_fetch_time(meta(expires), NOW) == expires + timedelta(seconds=1)


def test_expired_cache_means_fetch_now() -> None:
    assert next_fetch_time(meta(NOW - timedelta(seconds=5)), NOW) == NOW


def test_missing_expiry_uses_the_fallback_interval() -> None:
    assert next_fetch_time(meta(None), NOW) == NOW + timedelta(seconds=60)
    assert next_fetch_time(meta(None), NOW, fallback_s=30.0) == NOW + timedelta(seconds=30)


def test_absurd_expiry_is_capped() -> None:
    far = NOW + timedelta(hours=5)
    assert next_fetch_time(meta(far), NOW, max_wait_s=120.0) == NOW + timedelta(seconds=120)


def test_margin_is_configurable() -> None:
    expires = NOW + timedelta(seconds=10)
    assert next_fetch_time(meta(expires), NOW, margin_s=2.5) == expires + timedelta(seconds=2.5)
