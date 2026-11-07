"""Contest schedule: keep the stored upcoming contests current and detect changes."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.domain.contest import ContestPhase
from cpstands.sources.base import SourcePort

PLATFORM = "codeforces"
UPCOMING_DAYS = 14
UPCOMING_LIMIT = 8
FRESH_FOR_S = 900.0  # /upcoming re-reads the contest list when the stored one is older

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ContestChange:
    contest_id: int
    name: str
    kind: Literal["moved", "cancelled", "started"]


class ContestService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        source: SourcePort,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions = sessions
        self._source = source
        self._now = now
        self._clock = clock
        self._synced_at: float | None = None

    async def sync(self) -> list[ContestChange]:
        """Read the contest list, store it, and correct reminders for what changed."""
        listing = await self._source.list_contests()
        now = self._now()
        changes: list[ContestChange] = []
        async with self._sessions() as session, session.begin():
            known = {c.contest_id: c for c in await repos.stored_before_contests(session, PLATFORM)}
            seen: set[int] = set()
            for contest in listing.contests:
                previous = known.get(contest.external_id)
                if contest.phase is ContestPhase.FINISHED and previous is None:
                    continue  # old news, nothing was ever promised about it
                seen.add(contest.external_id)
                await repos.upsert_contest(
                    session,
                    PLATFORM,
                    contest.external_id,
                    contest.name,
                    contest.phase.value,
                    contest.starts_at,
                    contest.duration_s,
                )
                if previous is None:
                    continue
                change = await self._apply_change(session, previous, contest, now)
                if change is not None:
                    changes.append(change)
            for contest_id, previous in known.items():
                if contest_id not in seen:  # deleted from the list: treat as cancelled
                    await repos.upsert_contest(
                        session, PLATFORM, contest_id, previous.name, "CANCELLED",
                        previous.starts_at, previous.duration_s,
                    )  # fmt: skip
                    told = await repos.cancel_reminders(session, PLATFORM, contest_id)
                    await repos.queue_notice(
                        session, PLATFORM, contest_id, told, repos.NOTICE_CANCELLED, now=now
                    )
                    changes.append(ContestChange(contest_id, previous.name, "cancelled"))
            await repos.plan_reminders(session, PLATFORM, now=now)
        self._synced_at = self._clock()
        if changes:
            log.info("contest_changes", changes=[(c.contest_id, c.kind) for c in changes])
        return changes

    async def _apply_change(
        self,
        session: AsyncSession,
        previous: repos.ContestRow,
        contest: object,
        now: datetime,
    ) -> ContestChange | None:
        from cpstands.domain.contest import Contest

        assert isinstance(contest, Contest)
        cid = contest.external_id
        if contest.phase is ContestPhase.CANCELLED:
            told = await repos.cancel_reminders(session, PLATFORM, cid)
            await repos.queue_notice(session, PLATFORM, cid, told, repos.NOTICE_CANCELLED, now=now)
            return ContestChange(cid, contest.name, "cancelled")
        if contest.phase is not ContestPhase.BEFORE:
            await repos.cancel_reminders(session, PLATFORM, cid)
            return ContestChange(cid, contest.name, "started")
        if contest.starts_at is not None and contest.starts_at != previous.starts_at:
            told = await repos.reschedule_reminders(
                session, PLATFORM, cid, contest.starts_at, now=now
            )
            await repos.queue_notice(session, PLATFORM, cid, told, repos.NOTICE_MOVED, now=now)
            return ContestChange(cid, contest.name, "moved")
        return None

    async def plan(self) -> int:
        """Create the reminder rows that are missing (new chats, switched-on reminders)."""
        async with self._sessions() as session, session.begin():
            return await repos.plan_reminders(session, PLATFORM, now=self._now())

    async def upcoming(self) -> list[repos.ContestRow]:
        """The next contests, re-reading the list first when the stored one is stale."""
        if self._synced_at is None or self._clock() - self._synced_at > FRESH_FOR_S:
            await self.sync()
        now = self._now()
        async with self._sessions() as session:
            return await repos.upcoming_contests(
                session,
                PLATFORM,
                now=now,
                until=now + timedelta(days=UPCOMING_DAYS),
                limit=UPCOMING_LIMIT,
            )
