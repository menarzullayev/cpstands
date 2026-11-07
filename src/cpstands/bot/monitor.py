"""Operator alerts (NFR-010): the owner is told once, reminded rarely, and told when it is over."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.i18n import I18n, Translator
from cpstands.services import ops as ops_service
from cpstands.services.contests import PLATFORM
from cpstands.services.standings import StandingsService

log = structlog.get_logger(__name__)

STALE_AFTER_S = 180.0  # standings older than this during a contest
SEND_FAILURE_RATE = 0.05
SEND_SAMPLE_MIN = 10
SOURCE_ERROR_STREAK = 3
REPEAT_S = 1800.0  # an open problem is repeated at most this often
TICK_S = 30.0


class OperatorAlerts:
    def __init__(
        self,
        bot: Bot,
        sessions: async_sessionmaker[AsyncSession],
        ops: ops_service.OpsState,
        standings: StandingsService,
        i18n: I18n,
        owner_id: int | None,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._bot = bot
        self._sessions = sessions
        self._ops = ops
        self._standings = standings
        self._i18n = i18n
        self._owner = owner_id
        self._clock = clock
        self._now = now
        self._sleep = sleep

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("operator_alerts_failed", exc_info=True)
            await self._sleep(TICK_S)

    async def _say(self) -> Translator:
        async with self._sessions() as session:
            record = await repos.get_chat(session, self._owner) if self._owner else None
        return self._i18n.bound(record.language if record else None, "neutral")

    async def conditions(self, say: Translator) -> dict[str, str]:
        """Every problem that exists right now, keyed by rule (and subject)."""
        found: dict[str, str] = {}
        now = self._now()
        async with self._sessions() as session:
            shot = await ops_service.snapshot(session, now=now)
            contests = set(await repos.live_contest_ids(session, PLATFORM)) | set(
                await repos.active_contests_to_watch(session, PLATFORM)
            )
        if not self._ops.is_paused(PLATFORM):
            for contest_id in sorted(contests):
                age = self._standings.age_s(contest_id)
                if age is not None and age > STALE_AFTER_S:
                    found[f"stale:{contest_id}"] = say(
                        "ops-alert-stale", contest=str(contest_id), age=int(age)
                    )
            for name, health in self._ops.sources.items():
                if health.consecutive_errors >= SOURCE_ERROR_STREAK and not health.paused:
                    found[f"source:{name}"] = say(
                        "ops-alert-source", source=name, count=health.consecutive_errors
                    )
        if shot.overdue_reminders:
            found["late"] = say("ops-alert-late", count=shot.overdue_reminders)
        rate, samples = self._ops.send_failure_rate()
        if samples >= SEND_SAMPLE_MIN and rate > SEND_FAILURE_RATE:
            found["sends"] = say("ops-alert-sends", percent=round(rate * 100), count=samples)
        return found

    async def tick(self) -> int:
        """Evaluate the rules and message the owner; returns the number of messages sent."""
        if self._owner is None:
            return 0
        say = await self._say()
        current = await self.conditions(say)
        now = self._now()
        open_alerts = self._ops.open_alerts
        sent = 0
        for key, text in current.items():
            last = open_alerts.get(key)
            due = last is None or (now - last).total_seconds() >= REPEAT_S
            if due and await self._send(text):
                open_alerts[key] = now
                sent += 1
        for key in [k for k in open_alerts if k not in current]:
            if await self._send(say("ops-alert-resolved", rule=key)):
                del open_alerts[key]
                sent += 1
        return sent

    async def _send(self, text: str) -> bool:
        try:
            assert self._owner is not None
            await self._bot.send_message(self._owner, text)
        except Exception:
            log.warning("operator_alert_not_sent", exc_info=True)
            return False
        return True
