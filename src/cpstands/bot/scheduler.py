"""The scheduler loop: refresh the contest list, plan reminders, send the due ones."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot.reminders import ReminderSender
from cpstands.db import repos
from cpstands.services.contests import PLATFORM, ContestService
from cpstands.services.ops import OpsState
from cpstands.services.retention import RetentionService
from cpstands.sources.base import SourceError

log = structlog.get_logger(__name__)

TICK_S = 15.0
SYNC_EVERY_S = 600.0
SYNC_RETRY_S = 120.0
BATCH = 20
MAX_BATCHES_PER_TICK = 5


class Scheduler:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        contests: ContestService,
        sender: ReminderSender,
        *,
        retention: RetentionService | None = None,
        ops: OpsState | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sessions = sessions
        self._contests = contests
        self._sender = sender
        self._retention = retention
        self._ops = ops
        self._clock = clock
        self._now = now
        self._sleep = sleep
        self._next_sync = 0.0

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("scheduler_tick_failed", exc_info=True)
            await self._sleep(TICK_S)

    async def tick(self) -> int:
        """One pass; returns how many reminders were delivered."""
        if self._ops is not None:
            self._ops.beat("scheduler")
        if self._clock() >= self._next_sync:
            try:
                await self._contests.sync()
                self._next_sync = self._clock() + SYNC_EVERY_S
            except SourceError:
                log.warning("contest_sync_failed", exc_info=True)
                self._next_sync = self._clock() + SYNC_RETRY_S
        await self._contests.plan()
        if self._retention is not None:
            try:
                await self._retention.run_if_due()
            except Exception:
                log.error("retention_failed", exc_info=True)
        delivered = 0
        for _ in range(MAX_BATCHES_PER_TICK):
            async with self._sessions() as session, session.begin():
                claimed = await repos.claim_due_reminders(
                    session, PLATFORM, now=self._now(), limit=BATCH
                )
            if not claimed:
                break
            for reminder in claimed:
                if await self._sender.send(reminder):
                    delivered += 1
            if len(claimed) < BATCH:
                break  # also keeps a reminder that was put back from being retried at once
        return delivered
