"""When to fetch next: align polling to the platform's cache expiry, not to a short fixed interval.

Experiment M1 (docs/experiments/M1-standings-fetch.md) showed that Codeforces serves standings
from a proxy cache for about 60 s and reports the exact expiry in the ``Expires`` header.
Polling faster returns the same body, so the best schedule is "just after the cache expires":
one request per minute, and every response is a fresh generation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from cpstands.domain.contest import FetchMeta


def next_fetch_time(
    meta: FetchMeta,
    now: datetime,
    *,
    margin_s: float = 1.0,
    fallback_s: float = 60.0,
    max_wait_s: float = 120.0,
) -> datetime:
    """Return the earliest sensible time for the next fetch of the same resource.

    * a future ``Expires``: fetch ``margin_s`` after it (so the cache has really expired);
    * an ``Expires`` already in the past: fetch now;
    * no ``Expires``: wait ``fallback_s``;
    * never wait longer than ``max_wait_s`` (protects against absurd headers).
    """
    if meta.expires_at is None:
        target = now + timedelta(seconds=fallback_s)
    elif meta.expires_at <= now:
        target = now
    else:
        target = meta.expires_at + timedelta(seconds=margin_s)
    return min(target, now + timedelta(seconds=max_wait_s))
