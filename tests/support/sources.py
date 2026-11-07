"""Test doubles for the contest source."""

from __future__ import annotations

from collections.abc import Sequence

from cpstands.domain.contest import HandleResolution, handle_key
from cpstands.sources.base import RetryableSourceError


class FakeSource:
    """Knows a fixed set of handles; spelling is canonicalized like user.info does."""

    platform = "codeforces"

    def __init__(self, existing: Sequence[str], *, fail: bool = False) -> None:
        self._existing = {handle_key(h): h for h in existing}
        self.fail = fail
        self.calls = 0

    async def resolve_handles(self, handles: Sequence[str]) -> HandleResolution:
        self.calls += 1
        if self.fail:
            raise RetryableSourceError("down")
        known = {
            handle_key(h): self._existing[handle_key(h)]
            for h in handles
            if handle_key(h) in self._existing
        }
        unknown = tuple(h for h in handles if handle_key(h) not in self._existing)
        return HandleResolution(known=known, unknown=unknown)
