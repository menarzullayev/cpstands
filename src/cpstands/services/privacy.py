"""Deleting a chat's data on request (REQ-018) and the data-protection retention rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

CONFIRM_VALID_S = 600  # a delete confirmation may be used for ten minutes


@dataclass(frozen=True, slots=True)
class Deleted:
    handles: int
    reminders: int
    alerts: int
    live_messages: int


async def delete_chat_data(
    sessions: async_sessionmaker[AsyncSession], chat_id: int, *, now: datetime | None = None
) -> Deleted | None:
    """Remove everything keyed by this chat; returns ``None`` when nothing was stored.

    Watched handles, reminders, outbox rows and live-message records go with the chat row
    (``ON DELETE CASCADE``). The request itself is logged without any chat content.
    """
    moment = now or datetime.now(UTC)
    async with sessions() as session, session.begin():
        exists = (
            await session.execute(
                text("SELECT 1 FROM chats WHERE chat_id = :c FOR UPDATE"), {"c": chat_id}
            )
        ).first()
        if exists is None:
            return None

        async def count(table: str) -> int:
            result = await session.execute(
                text(f"SELECT count(*) FROM {table} WHERE chat_id = :c"),  # noqa: S608 - fixed names
                {"c": chat_id},
            )
            return int(result.scalar_one())

        deleted = Deleted(
            handles=await count("watched_handles"),
            reminders=await count("reminders"),
            alerts=await count("deliveries"),
            live_messages=await count("standings_messages"),
        )
        request_id = (
            await session.execute(
                text(
                    "INSERT INTO deletion_requests (subject_type, subject_id, requested_at) "
                    "VALUES ('chat', :c, CAST(:now AS timestamptz)) RETURNING id"
                ),
                {"c": chat_id, "now": moment},
            )
        ).scalar_one()
        await session.execute(text("DELETE FROM chats WHERE chat_id = :c"), {"c": chat_id})
        await session.execute(
            text(
                "UPDATE deletion_requests SET completed_at = CAST(:now AS timestamptz) "
                "WHERE id = :id"
            ),
            {"now": moment, "id": request_id},
        )
    return deleted
