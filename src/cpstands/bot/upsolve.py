"""The upsolve watcher: polls the submissions of followed handles for a while after contests."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.services.ops import OpsState
from cpstands.services.upsolve import WINDOW, UpsolveService
from cpstands.sources.base import PermanentSourceError, SourceError, SourcePort

log = structlog.get_logger(__name__)

TICK_S = 20.0
PER_HANDLE_S = 600.0  # every followed handle is looked at about every ten minutes
MAX_PER_TICK = 5
RETRY_S = 180.0
GONE_S = 3600.0
MAX_CONTESTS = 40


class UpsolveWatcher:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        source: SourcePort,
        service: UpsolveService,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        ops: OpsState | None = None,
    ) -> None:
        self._sessions = sessions
        self._source = source
        self._service = service
        self._clock = clock
        self._now = now
        self._sleep = sleep
        self._ops = ops
        self._next_at: dict[str, float] = {}

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("upsolve_tick_failed", exc_info=True)
            await self._sleep(TICK_S)

    async def tick(self) -> int:
        """Look at the handles that are due; returns how many alerts were queued."""
        if self._ops is not None:
            self._ops.beat("upsolve")
        now = self._now()
        async with self._sessions() as session:
            recent = await repos.finished_contests(
                session,
                self._service.platform,
                ended_after=now - WINDOW,
                now=now,
                limit=MAX_CONTESTS,
            )
            targets = await repos.upsolve_targets(session, self._service.platform) if recent else {}
        for gone in set(self._next_at) - set(targets):
            del self._next_at[gone]
        if not targets:
            return 0
        contests = {c.contest_id: c for c in recent}
        due = sorted(
            (key for key in targets if self._next_at.get(key, 0.0) <= self._clock()),
            key=lambda key: (self._next_at.get(key, 0.0), key),
        )[:MAX_PER_TICK]
        queued = 0
        for key in due:
            self._next_at[key] = self._clock() + PER_HANDLE_S
            try:
                submissions = await self._source.fetch_user_submissions(targets[key])
            except PermanentSourceError:
                self._next_at[key] = self._clock() + GONE_S
                continue
            except SourceError:
                log.warning("upsolve_fetch_failed", handle=key)
                self._next_at[key] = self._clock() + RETRY_S
                continue
            queued += await self._service.process(targets[key], submissions, contests)
        return queued
