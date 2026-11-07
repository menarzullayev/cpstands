from __future__ import annotations

import asyncio
import itertools
import random

import pytest

from cpstands.sources.base import CircuitOpenError
from cpstands.sources.governor import CircuitBreaker, RateGovernor, backoff_delay
from tests.support.clock import FakeClock


async def test_first_request_does_not_wait() -> None:
    clock = FakeClock()
    governor = RateGovernor(2.0, clock=clock, rng=random.Random(1))
    assert await governor.acquire() == 0.0
    assert clock.sleeps == []


async def test_requests_are_spaced_at_least_the_minimum_interval() -> None:
    clock = FakeClock()
    governor = RateGovernor(2.0, clock=clock, rng=random.Random(1))
    starts = []
    for _ in range(5):
        await governor.acquire()
        starts.append(clock.now)
    gaps = [b - a for a, b in itertools.pairwise(starts)]
    assert all(gap >= 2.0 for gap in gaps)
    assert all(gap <= 2.0 * 1.25 + 1e-9 for gap in gaps)


async def test_time_already_passed_counts_towards_the_interval() -> None:
    clock = FakeClock()
    governor = RateGovernor(2.0, jitter_fraction=0.0, clock=clock)
    await governor.acquire()
    clock.advance(5.0)
    assert await governor.acquire() == 0.0


async def test_concurrent_callers_are_serialized() -> None:
    clock = FakeClock()
    governor = RateGovernor(2.0, jitter_fraction=0.0, clock=clock)
    starts: list[float] = []

    async def worker() -> None:
        await governor.acquire()
        starts.append(clock.now)

    await asyncio.gather(*(worker() for _ in range(4)))
    gaps = [b - a for a, b in itertools.pairwise(starts)]
    assert gaps == [2.0, 2.0, 2.0]


def test_backoff_grows_exponentially_and_is_capped() -> None:
    rng = random.Random(7)
    delays = [
        backoff_delay(n, base_s=2.0, cap_s=60.0, jitter_fraction=0.0, rng=rng) for n in range(8)
    ]
    assert delays[:4] == [2.0, 4.0, 8.0, 16.0]
    assert delays[-1] == 60.0


def test_backoff_jitter_stays_inside_its_bounds() -> None:
    rng = random.Random(3)
    for _ in range(200):
        delay = backoff_delay(2, base_s=2.0, cap_s=60.0, jitter_fraction=0.25, rng=rng)
        assert 8.0 * 0.75 <= delay <= 8.0 * 1.25


def test_breaker_opens_after_threshold_and_blocks_calls() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("m", threshold=3, cooldown_s=30.0, clock=clock)
    for _ in range(2):
        breaker.before_call()
        breaker.record_failure()
    assert breaker.state == "closed"
    breaker.before_call()
    breaker.record_failure()
    assert breaker.state == "open"
    with pytest.raises(CircuitOpenError) as info:
        breaker.before_call()
    assert 0 < info.value.retry_in_s <= 30.0


def test_breaker_half_open_allows_one_trial_then_closes_on_success() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("m", threshold=1, cooldown_s=30.0, clock=clock)
    breaker.before_call()
    breaker.record_failure()
    clock.advance(31.0)
    assert breaker.state == "half-open"
    breaker.before_call()  # the trial
    with pytest.raises(CircuitOpenError):
        breaker.before_call()  # a second concurrent call is refused
    breaker.record_success()
    assert breaker.state == "closed"
    breaker.before_call()


def test_breaker_reopens_when_the_trial_fails() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("m", threshold=1, cooldown_s=30.0, clock=clock)
    breaker.before_call()
    breaker.record_failure()
    clock.advance(31.0)
    breaker.before_call()
    breaker.record_failure()
    assert breaker.state == "open"
    with pytest.raises(CircuitOpenError):
        breaker.before_call()


def test_success_resets_the_failure_count() -> None:
    breaker = CircuitBreaker("m", threshold=3, clock=FakeClock())
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == "closed"
