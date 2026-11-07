"""Retention jobs (ADR-014): contest data and removed chats are kept 30 days at most."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

RETENTION_DAYS = 30
RUN_EVERY = timedelta(hours=24)
STATE_KEY = "retention.last_run"

log = structlog.get_logger(__name__)

# (label, SQL); every statement takes :cut, the moment before which rows are too old.
_RULES: tuple[tuple[str, str], ...] = (
    ("participant_results", "DELETE FROM participant_results WHERE updated_at < CAST(:cut AS timestamptz)"),
    ("solve_events", "DELETE FROM solve_events WHERE created_at < CAST(:cut AS timestamptz)"),
    ("contests", "DELETE FROM contests WHERE updated_at < CAST(:cut AS timestamptz)"),
    (
        "reminders",
        "DELETE FROM reminders WHERE state IN ('sent','cancelled','skipped') "
        "AND due_at < CAST(:cut AS timestamptz)",
    ),
    (
        "deliveries",
        "DELETE FROM deliveries WHERE state IN ('sent','failed') "
        "AND not_before < CAST(:cut AS timestamptz)",
    ),
    (
        "standings_messages",
        "DELETE FROM standings_messages WHERE state IN ('frozen','orphaned') "
        "AND (last_edit_at IS NULL OR last_edit_at < CAST(:cut AS timestamptz))",
    ),
    (
        "removed_chats",
        "DELETE FROM chats WHERE status IN ('removed','deleted') "
        "AND updated_at < CAST(:cut AS timestamptz)",
    ),
    (
        "deletion_requests",
        "DELETE FROM deletion_requests WHERE completed_at IS NOT NULL "
        "AND completed_at < CAST(:cut AS timestamptz)",
    ),
)  # fmt: skip


class RetentionService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        days: int = RETENTION_DAYS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._days = days
        self._now = now

    async def run(self) -> dict[str, int]:
        """Delete everything older than the retention window; returns rows removed per rule."""
        now = self._now()
        cut = now - timedelta(days=self._days)
        removed: dict[str, int] = {}
        async with self._sessions() as session, session.begin():
            for label, sql in _RULES:
                result = await session.execute(text(sql), {"cut": cut})
                removed[label] = int(result.rowcount or 0)  # type: ignore[attr-defined]
            await session.execute(
                text(
                    "INSERT INTO runtime_state (key, value) VALUES (:k, to_jsonb(CAST(:v AS text))) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                ),
                {"k": STATE_KEY, "v": now.isoformat()},
            )
        log.info("retention_done", **removed)
        return removed

    async def run_if_due(self) -> dict[str, int] | None:
        """Run at most once a day, also across restarts (the last run is stored)."""
        async with self._sessions() as session:
            row = (
                await session.execute(
                    text("SELECT value #>> '{}' FROM runtime_state WHERE key = :k"),
                    {"k": STATE_KEY},
                )
            ).first()
        if row is not None and row[0]:
            last = datetime.fromisoformat(str(row[0]))
            if self._now() - last < RUN_EVERY:
                return None
        return await self.run()
