"""Request pacing, backoff and circuit breaking for upstream APIs (REQ-N07, ADR-004).

Everything time-related goes through a ``Clock`` so tests run instantly and deterministically.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Protocol

from cpstands.sources.base import CircuitOpenError


class Clock(Protocol):
    def monotonic(self) -> float: ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


@dataclass
class RateGovernor:
    """Serializes request starts so that two starts are at least ``min_interval_s`` apart.

    A random extra delay of up to ``jitter_fraction`` of the interval is added so that several
    instances do not synchronize. The documented Codeforces limit is about one request per two
    seconds (EVID-012); the configuration refuses lower values.
    """

    min_interval_s: float
    jitter_fraction: float = 0.25
    clock: Clock = field(default_factory=SystemClock)
    rng: random.Random = field(default_factory=random.Random)
    _next_at: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def acquire(self) -> float:
        """Wait until a request may start; return the seconds waited."""
        async with self._lock:
            now = self.clock.monotonic()
            waited = max(0.0, self._next_at - now)
            if waited > 0:
                await self.clock.sleep(waited)
            start = self.clock.monotonic()
            self._next_at = start + self.min_interval_s * (
                1.0 + self.jitter_fraction * self.rng.random()
            )
            return waited


def backoff_delay(
    attempt: int, *, base_s: float, cap_s: float, jitter_fraction: float, rng: random.Random
) -> float:
    """Exponential backoff with symmetric jitter: ``min(cap, base * 2**attempt)`` +/- jitter."""
    raw = min(cap_s, base_s * (2.0**attempt))
    return raw * (1.0 + jitter_fraction * (rng.random() * 2.0 - 1.0))


@dataclass
class CircuitBreaker:
    """Closed -> open after ``threshold`` consecutive failures -> half-open after ``cooldown_s``."""

    name: str
    threshold: int = 3
    cooldown_s: float = 30.0
    clock: Clock = field(default_factory=SystemClock)
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _half_open: bool = field(default=False, init=False)

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self._half_open or self.clock.monotonic() - self._opened_at >= self.cooldown_s:
            return "half-open"
        return "open"

    def before_call(self) -> None:
        """Raise ``CircuitOpenError`` while open; allow exactly one trial call when half-open."""
        if self._opened_at is None:
            return
        elapsed = self.clock.monotonic() - self._opened_at
        if elapsed < self.cooldown_s:
            raise CircuitOpenError(self.name, self.cooldown_s - elapsed)
        if self._half_open:
            raise CircuitOpenError(self.name, self.cooldown_s)
        self._half_open = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._half_open or self._failures >= self.threshold:
            self._opened_at = self.clock.monotonic()
            self._half_open = False
