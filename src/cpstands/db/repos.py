"""Queries over the chat and watch-list tables; every function takes the caller's session."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import RowMapping, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cpstands.db.schema import chats, watched_handles


@dataclass(frozen=True, slots=True)
class ChatRecord:
    chat_id: int
    chat_type: str
    language: str | None
    time_zone: str | None
    tone: str
    status: str


_CHAT_COLUMNS = (
    chats.c.chat_id,
    chats.c.chat_type,
    chats.c.language,
    chats.c.time_zone,
    chats.c.tone,
    chats.c.status,
)


def _record(row: RowMapping) -> ChatRecord:
    return ChatRecord(
        chat_id=int(row["chat_id"]),
        chat_type=str(row["chat_type"]),
        language=row["language"] if isinstance(row["language"], str) else None,
        time_zone=row["time_zone"] if isinstance(row["time_zone"], str) else None,
        tone=str(row["tone"]),
        status=str(row["status"]),
    )


async def upsert_chat(session: AsyncSession, chat_id: int, chat_type: str) -> ChatRecord:
    """Create the chat or refresh its type; a chat that was removed starts onboarding again."""
    base = insert(chats).values(chat_id=chat_id, chat_type=chat_type)
    statement = base.on_conflict_do_update(
        index_elements=[chats.c.chat_id],
        set_={
            "chat_type": base.excluded.chat_type,
            "status": text(
                "CASE WHEN chats.status IN ('removed','deleted') "
                "THEN 'onboarding' ELSE chats.status END"
            ),
            "updated_at": func.now(),
        },
    ).returning(*_CHAT_COLUMNS)
    result = await session.execute(statement)
    return _record(result.mappings().one())


async def get_chat(
    session: AsyncSession, chat_id: int, *, for_update: bool = False
) -> ChatRecord | None:
    query = select(*_CHAT_COLUMNS).where(chats.c.chat_id == chat_id)
    if for_update:
        query = query.with_for_update()
    row = (await session.execute(query)).mappings().first()
    return _record(row) if row else None


async def _update_chat(session: AsyncSession, chat_id: int, **values: object) -> bool:
    result = await session.execute(
        update(chats)
        .where(chats.c.chat_id == chat_id)
        .values(updated_at=func.now(), **values)
        .returning(chats.c.chat_id)
    )
    return result.first() is not None


async def set_language(session: AsyncSession, chat_id: int, language: str) -> bool:
    return await _update_chat(session, chat_id, language=language)


async def set_time_zone(session: AsyncSession, chat_id: int, time_zone: str) -> bool:
    return await _update_chat(session, chat_id, time_zone=time_zone)


async def set_tone(session: AsyncSession, chat_id: int, tone: str) -> bool:
    return await _update_chat(session, chat_id, tone=tone)


async def set_status(session: AsyncSession, chat_id: int, status: str) -> bool:
    return await _update_chat(session, chat_id, status=status)


async def count_handles(session: AsyncSession, chat_id: int, platform: str) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(watched_handles)
        .where(watched_handles.c.chat_id == chat_id, watched_handles.c.platform == platform)
    )
    return int(result.scalar_one())


async def list_handles(session: AsyncSession, chat_id: int, platform: str) -> list[tuple[str, str]]:
    """Return ``(handle_key, handle_display)`` pairs sorted by key."""
    result = await session.execute(
        select(watched_handles.c.handle_key, watched_handles.c.handle_display)
        .where(watched_handles.c.chat_id == chat_id, watched_handles.c.platform == platform)
        .order_by(watched_handles.c.handle_key)
    )
    return [(str(key), str(display)) for key, display in result.all()]


async def add_handles(
    session: AsyncSession, chat_id: int, platform: str, handles: Mapping[str, str]
) -> set[str]:
    """Insert ``key -> display`` pairs; returns the keys that were really new."""
    if not handles:
        return set()
    statement = (
        insert(watched_handles)
        .values(
            [
                {
                    "chat_id": chat_id,
                    "platform": platform,
                    "handle_key": key,
                    "handle_display": display,
                }
                for key, display in handles.items()
            ]
        )
        .on_conflict_do_nothing()
        .returning(watched_handles.c.handle_key)
    )
    return {str(key) for (key,) in (await session.execute(statement)).all()}


async def remove_handles(
    session: AsyncSession, chat_id: int, platform: str, keys: Sequence[str]
) -> dict[str, str]:
    """Delete the given keys; returns ``key -> display`` for those that existed."""
    if not keys:
        return {}
    result = await session.execute(
        delete(watched_handles)
        .where(
            watched_handles.c.chat_id == chat_id,
            watched_handles.c.platform == platform,
            watched_handles.c.handle_key.in_(list(keys)),
        )
        .returning(watched_handles.c.handle_key, watched_handles.c.handle_display)
    )
    return {str(key): str(display) for key, display in result.all()}
