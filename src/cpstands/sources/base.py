"""The contest-source contract (ADR-004) and the error taxonomy shared by all sources."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from cpstands.domain.contest import (
    ContestList,
    FullStandings,
    HandleResolution,
    RatingResult,
    StandingsFetch,
)


class SourceError(Exception):
    """Base class of every source failure."""


class RetryableSourceError(SourceError):
    """A failure that may succeed on retry: timeouts, 5xx, rate limiting, truncated bodies."""

    def __init__(self, message: str, *, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class PermanentSourceError(SourceError):
    """A failure that retrying will not fix: bad request, unknown contest, unexpected format."""


class UnknownHandleError(PermanentSourceError):
    def __init__(self, handle: str) -> None:
        super().__init__(f"unknown handle: {handle}")
        self.handle = handle


class SourceFormatError(PermanentSourceError):
    """The response parsed as HTTP but not as the documented data shape."""


class ResponseTooLargeError(PermanentSourceError):
    """The body exceeded the configured safety limit."""


class CircuitOpenError(SourceError):
    """The circuit breaker is open: calls are refused until the cooldown ends."""

    def __init__(self, name: str, retry_in_s: float) -> None:
        super().__init__(f"circuit open for {name}; retry in {retry_in_s:.0f}s")
        self.name = name
        self.retry_in_s = retry_in_s


@runtime_checkable
class SourcePort(Protocol):
    """What the rest of the system may ask of a contest platform."""

    platform: str

    async def list_contests(self) -> ContestList: ...

    async def fetch_standings(self, contest_id: int, watched: frozenset[str]) -> StandingsFetch: ...

    async def fetch_full_standings(self, contest_id: int) -> FullStandings: ...

    async def fetch_ratings(self, handles: Sequence[str]) -> RatingResult: ...

    async def resolve_handles(self, handles: Sequence[str]) -> HandleResolution: ...
