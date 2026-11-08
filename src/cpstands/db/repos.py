"""Queries over the chat and watch-list tables; every function takes the caller's session."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import RowMapping, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cpstands.db.schema import (
    chats,
    contests,
    deliveries,
    participant_results,
    solve_events,
    standings_messages,
    watched_handles,
)


@dataclass(frozen=True, slots=True)
class ChatRecord:
    chat_id: int
    chat_type: str
    language: str | None
    time_zone: str | None
    tone: str
    status: str
    reminder_offsets: tuple[int, ...]
    alerts_enabled: bool
    notify_level: int = 4
    table_cols: int = 16
    summary_enabled: bool = True


_CHAT_COLUMNS = (
    chats.c.chat_id,
    chats.c.chat_type,
    chats.c.language,
    chats.c.time_zone,
    chats.c.tone,
    chats.c.status,
    chats.c.reminder_offsets,
    chats.c.alerts_enabled,
    chats.c.notify_level,
    chats.c.table_cols,
    chats.c.summary_enabled,
)


def _record(row: RowMapping) -> ChatRecord:
    return ChatRecord(
        chat_id=int(row["chat_id"]),
        chat_type=str(row["chat_type"]),
        language=row["language"] if isinstance(row["language"], str) else None,
        time_zone=row["time_zone"] if isinstance(row["time_zone"], str) else None,
        tone=str(row["tone"]),
        status=str(row["status"]),
        reminder_offsets=tuple(int(v) for v in row["reminder_offsets"] or ()),
        alerts_enabled=bool(row["alerts_enabled"]),
        notify_level=int(row["notify_level"]),
        table_cols=int(row["table_cols"]),
        summary_enabled=bool(row["summary_enabled"]),
    )


async def upsert_chat(
    session: AsyncSession, chat_id: int, chat_type: str, title: str | None = None
) -> ChatRecord:
    """Create the chat or refresh its type and title; a removed chat starts onboarding again."""
    base = insert(chats).values(chat_id=chat_id, chat_type=chat_type, title=title)
    statement = base.on_conflict_do_update(
        index_elements=[chats.c.chat_id],
        set_={
            "chat_type": base.excluded.chat_type,
            "title": func.coalesce(base.excluded.title, chats.c.title),
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


async def set_reminder_offsets(session: AsyncSession, chat_id: int, offsets: Sequence[int]) -> bool:
    """Set the reminder offsets in minutes before the start; an empty list turns them off.

    Scheduled reminders whose offset was deselected are cancelled; the planner creates the
    ones that were added (and revives cancelled ones whose moment is still ahead).
    """
    ordered = sorted({int(o) for o in offsets}, reverse=True)
    ok = await _update_chat(session, chat_id, reminder_offsets=ordered)
    if ok:
        await session.execute(
            text(
                "UPDATE reminders SET state = 'cancelled' "
                "WHERE chat_id = :chat AND state = 'scheduled' AND offset_min > 0 "
                "AND NOT (offset_min = ANY(CAST(:keep AS integer[])))"
            ),
            {"chat": chat_id, "keep": ordered},
        )
    return ok


async def set_table_cols(session: AsyncSession, chat_id: int, cols: int) -> bool:
    return await _update_chat(session, chat_id, table_cols=cols)


async def set_summary_enabled(session: AsyncSession, chat_id: int, enabled: bool) -> bool:
    return await _update_chat(session, chat_id, summary_enabled=enabled)


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
    level = (
        await session.execute(select(chats.c.notify_level).where(chats.c.chat_id == chat_id))
    ).scalar()
    toggles = LEVEL_TOGGLES[int(level) if level is not None else 4]
    statement = (
        insert(watched_handles)
        .values(
            [
                {
                    "chat_id": chat_id,
                    "platform": platform,
                    "handle_key": key,
                    "handle_display": display,
                    **toggles,
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


# --- live standings messages ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiveMessage:
    chat_id: int
    contest_id: int
    message_id: int
    row_page: int
    col_page: int
    last_hash: str | None
    last_edit_at: datetime | None
    view: str = "auto"


async def register_live_message(
    session: AsyncSession,
    chat_id: int,
    platform: str,
    contest_id: int,
    message_id: int,
    *,
    max_live: int,
) -> None:
    """Make ``message_id`` the live standings message of this chat and contest.

    An older message of the same contest stops updating. When a chat has more than
    ``max_live`` live messages, the least recently refreshed ones are frozen.
    """
    base = insert(standings_messages).values(
        chat_id=chat_id,
        platform=platform,
        contest_id=contest_id,
        message_id=message_id,
        state="active",
        row_page=0,
        col_page=0,
        view="auto",
        last_hash=None,
        last_edit_at=func.now(),
        dirty=False,
    )
    await session.execute(
        base.on_conflict_do_update(
            index_elements=["chat_id", "platform", "contest_id"],
            set_={
                "message_id": message_id,
                "state": "active",
                "row_page": 0,
                "col_page": 0,
                "view": "auto",
                "last_hash": None,
                "last_edit_at": func.now(),
                "dirty": False,
            },
        )
    )
    keep = (
        select(standings_messages.c.contest_id)
        .where(
            standings_messages.c.chat_id == chat_id,
            standings_messages.c.platform == platform,
            standings_messages.c.state == "active",
        )
        .order_by(standings_messages.c.last_edit_at.desc())
        .limit(max_live)
    )
    await session.execute(
        update(standings_messages)
        .where(
            standings_messages.c.chat_id == chat_id,
            standings_messages.c.platform == platform,
            standings_messages.c.state == "active",
            standings_messages.c.contest_id.not_in(keep),
        )
        .values(state="frozen")
    )


async def set_live_pages(
    session: AsyncSession,
    chat_id: int,
    platform: str,
    contest_id: int,
    message_id: int,
    row_page: int,
    col_page: int,
    view: str = "auto",
) -> bool:
    """Remember the page and view the reader chose; ignored when another message took over."""
    result = await session.execute(
        update(standings_messages)
        .where(
            standings_messages.c.chat_id == chat_id,
            standings_messages.c.platform == platform,
            standings_messages.c.contest_id == contest_id,
            standings_messages.c.message_id == message_id,
        )
        .values(row_page=row_page, col_page=col_page, view=view)
        .returning(standings_messages.c.chat_id)
    )
    return result.first() is not None


async def live_contest_ids(session: AsyncSession, platform: str) -> list[int]:
    result = await session.execute(
        select(standings_messages.c.contest_id)
        .join(chats, chats.c.chat_id == standings_messages.c.chat_id)
        .where(
            standings_messages.c.platform == platform,
            standings_messages.c.state == "active",
            chats.c.status.in_(("onboarding", "active")),
        )
        .distinct()
    )
    return [int(row[0]) for row in result.all()]


async def live_messages(session: AsyncSession, platform: str, contest_id: int) -> list[LiveMessage]:
    result = await session.execute(
        select(
            standings_messages.c.chat_id,
            standings_messages.c.contest_id,
            standings_messages.c.message_id,
            standings_messages.c.row_page,
            standings_messages.c.col_page,
            standings_messages.c.last_hash,
            standings_messages.c.last_edit_at,
            standings_messages.c.view,
        ).where(
            standings_messages.c.platform == platform,
            standings_messages.c.contest_id == contest_id,
            standings_messages.c.state == "active",
            standings_messages.c.message_id.is_not(None),
        )
    )
    return [LiveMessage(*row) for row in result.all()]


async def mark_live_message(
    session: AsyncSession,
    platform: str,
    message: LiveMessage,
    *,
    state: str | None = None,
    last_hash: str | None = None,
    edited: bool = False,
) -> None:
    values: dict[str, object] = {}
    if state is not None:
        values["state"] = state
    if last_hash is not None:
        values["last_hash"] = last_hash
    if edited:
        values["last_edit_at"] = func.now()
    if not values:
        return
    await session.execute(
        update(standings_messages)
        .where(
            standings_messages.c.chat_id == message.chat_id,
            standings_messages.c.platform == platform,
            standings_messages.c.contest_id == message.contest_id,
            standings_messages.c.message_id == message.message_id,
        )
        .values(**values)
    )


# --- contests ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContestRow:
    contest_id: int
    name: str
    phase: str
    starts_at: datetime | None
    duration_s: int | None


def _contest_row(row: Sequence[object]) -> ContestRow:
    return ContestRow(
        contest_id=int(row[0]),  # type: ignore[call-overload]
        name=str(row[1]),
        phase=str(row[2]),
        starts_at=row[3] if isinstance(row[3], datetime) else None,
        duration_s=int(row[4]) if isinstance(row[4], int) else None,
    )


_CONTEST_COLUMNS = (
    contests.c.external_id,
    contests.c.name,
    contests.c.phase,
    contests.c.starts_at,
    contests.c.duration_s,
)


async def get_contest(session: AsyncSession, platform: str, contest_id: int) -> ContestRow | None:
    row = (
        await session.execute(
            select(*_CONTEST_COLUMNS).where(
                contests.c.platform == platform, contests.c.external_id == contest_id
            )
        )
    ).first()
    return _contest_row(row) if row else None


async def upsert_contest(
    session: AsyncSession,
    platform: str,
    contest_id: int,
    name: str,
    phase: str,
    starts_at: datetime | None,
    duration_s: int | None,
) -> ContestRow | None:
    """Store the contest and return what was stored before (``None`` when it is new)."""
    previous = await get_contest(session, platform, contest_id)
    statement = insert(contests).values(
        platform=platform,
        external_id=contest_id,
        name=name,
        phase=phase,
        starts_at=starts_at,
        duration_s=duration_s,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["platform", "external_id"],
            set_={
                "name": name,
                "phase": phase,
                "starts_at": starts_at,
                "duration_s": duration_s,
                "updated_at": func.now(),
            },
        )
    )
    return previous


async def upcoming_contests(
    session: AsyncSession, platform: str, *, now: datetime, until: datetime, limit: int
) -> list[ContestRow]:
    result = await session.execute(
        select(*_CONTEST_COLUMNS)
        .where(
            contests.c.platform == platform,
            contests.c.phase == "BEFORE",
            contests.c.starts_at > now,
            contests.c.starts_at <= until,
        )
        .order_by(contests.c.starts_at, contests.c.external_id)
        .limit(limit)
    )
    return [_contest_row(row) for row in result.all()]


async def stored_before_contests(session: AsyncSession, platform: str) -> list[ContestRow]:
    result = await session.execute(
        select(*_CONTEST_COLUMNS).where(
            contests.c.platform == platform, contests.c.phase == "BEFORE"
        )
    )
    return [_contest_row(row) for row in result.all()]


async def finished_contests(
    session: AsyncSession, platform: str, *, ended_after: datetime, now: datetime, limit: int
) -> list[ContestRow]:
    """Finished contests that ended within the window, newest first."""
    result = await session.execute(
        text(
            """
            SELECT c.external_id, c.name, c.phase, c.starts_at, c.duration_s FROM contests c
            WHERE c.platform = :platform AND c.phase = 'FINISHED'
              AND c.starts_at IS NOT NULL AND c.duration_s IS NOT NULL
              AND c.starts_at + c.duration_s * interval '1 second' > CAST(:after AS timestamptz)
              AND c.starts_at + c.duration_s * interval '1 second' <= CAST(:now AS timestamptz)
            ORDER BY c.starts_at DESC, c.external_id DESC
            LIMIT :limit
            """
        ),
        {"platform": platform, "after": ended_after, "now": now, "limit": limit},
    )
    return [_contest_row(row) for row in result.all()]


async def latest_finished_contests(
    session: AsyncSession, platform: str, *, limit: int
) -> list[ContestRow]:
    result = await session.execute(
        select(*_CONTEST_COLUMNS)
        .where(contests.c.platform == platform, contests.c.phase == "FINISHED")
        .order_by(contests.c.starts_at.desc().nulls_last(), contests.c.external_id.desc())
        .limit(limit)
    )
    return [_contest_row(row) for row in result.all()]


# --- reminders --------------------------------------------------------------------------

# Offsets below one are not time offsets but notices about a change of the contest.
NOTICE_MOVED = -1
NOTICE_CANCELLED = -2
STALE_AFTER_MIN = 30  # a reminder this late is skipped rather than sent


@dataclass(frozen=True, slots=True)
class ClaimedReminder:
    chat_id: int
    contest_id: int
    offset_min: int
    attempts: int
    due_at: datetime


async def plan_reminders(
    session: AsyncSession,
    platform: str,
    *,
    now: datetime,
    horizon_days: int = 30,
    followers_only: bool = False,
) -> int:
    """Create the missing reminder rows of every active chat; safe to run again and again.

    An offset whose moment has already passed is stored as ``skipped``, so it is never sent late
    and never planned twice. Rows that were cancelled (reminders switched off and on again)
    become scheduled again when their moment is still ahead. With ``followers_only`` only
    channels and the chats that follow a handle of this platform are reminded.
    """
    result = await session.execute(
        text(
            """
            INSERT INTO reminders (chat_id, platform, contest_id, offset_min, due_at, state)
            SELECT ch.chat_id, c.platform, c.external_id, off,
                   c.starts_at - make_interval(mins => off),
                   CASE WHEN c.starts_at - make_interval(mins => off) <= CAST(:now AS timestamptz)
                        THEN 'skipped' ELSE 'scheduled' END
            FROM chats ch
            JOIN contests c ON c.platform = :platform
            CROSS JOIN LATERAL unnest(ch.reminder_offsets) AS off
            WHERE ch.status = 'active'
              AND (NOT CAST(:followers AS boolean) OR ch.chat_type = 'channel' OR EXISTS (
                    SELECT 1 FROM watched_handles w
                    WHERE w.chat_id = ch.chat_id AND w.platform = c.platform))
              AND c.phase = 'BEFORE'
              AND c.starts_at > CAST(:now AS timestamptz)
              AND c.starts_at <= CAST(:now AS timestamptz) + make_interval(days => :days)
              AND off > 0
            ON CONFLICT (chat_id, platform, contest_id, offset_min) DO UPDATE
              SET state = 'scheduled', due_at = EXCLUDED.due_at
              WHERE reminders.state = 'cancelled' AND EXCLUDED.due_at > CAST(:now AS timestamptz)
            """
        ),
        {"platform": platform, "now": now, "days": horizon_days, "followers": followers_only},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def reschedule_reminders(
    session: AsyncSession, platform: str, contest_id: int, starts_at: datetime, *, now: datetime
) -> list[int]:
    """Move unsent reminders to the new start time; returns the chats that were already told.

    Reminders that were sent stay sent. Those chats get a notice about the new time.
    """
    await session.execute(
        text(
            """
            UPDATE reminders
            SET due_at = CAST(:start AS timestamptz) - make_interval(mins => offset_min),
                state = CASE WHEN CAST(:start AS timestamptz) - make_interval(mins => offset_min) <= CAST(:now AS timestamptz)
                             THEN 'skipped' ELSE 'scheduled' END
            WHERE platform = :platform AND contest_id = :cid AND offset_min > 0
              AND state IN ('scheduled', 'skipped')
            """
        ),
        {"platform": platform, "cid": contest_id, "start": starts_at, "now": now},
    )
    return await _told_chats(session, platform, contest_id)


async def cancel_reminders(session: AsyncSession, platform: str, contest_id: int) -> list[int]:
    """Withdraw unsent reminders; returns the chats that were already told."""
    await session.execute(
        text(
            "UPDATE reminders SET state = 'cancelled' "
            "WHERE platform = :platform AND contest_id = :cid "
            "AND offset_min > 0 AND state = 'scheduled'"
        ),
        {"platform": platform, "cid": contest_id},
    )
    return await _told_chats(session, platform, contest_id)


async def _told_chats(session: AsyncSession, platform: str, contest_id: int) -> list[int]:
    result = await session.execute(
        text(
            "SELECT DISTINCT chat_id FROM reminders "
            "WHERE platform = :platform AND contest_id = :cid AND offset_min > 0 "
            "AND state = 'sent'"
        ),
        {"platform": platform, "cid": contest_id},
    )
    return [int(row[0]) for row in result.all()]


async def queue_notice(
    session: AsyncSession,
    platform: str,
    contest_id: int,
    chat_ids: Sequence[int],
    kind: int,
    *,
    now: datetime,
) -> None:
    """Schedule a "moved" or "cancelled" notice for chats that already got a reminder."""
    for chat_id in chat_ids:
        await session.execute(
            text(
                """
                INSERT INTO reminders (chat_id, platform, contest_id, offset_min, due_at, state)
                VALUES (:chat, :platform, :cid, :kind, CAST(:now AS timestamptz), 'scheduled')
                ON CONFLICT (chat_id, platform, contest_id, offset_min) DO UPDATE
                  SET state = 'scheduled', due_at = EXCLUDED.due_at, sent_at = NULL, attempts = 0
                """
            ),
            {"chat": chat_id, "platform": platform, "cid": contest_id, "kind": kind, "now": now},
        )


async def claim_due_reminders(
    session: AsyncSession, platform: str, *, now: datetime, limit: int
) -> list[ClaimedReminder]:
    """Take the due reminders and mark them sent *before* sending: at most once per offset.

    ``FOR UPDATE SKIP LOCKED`` lets several workers claim without seeing the same row.
    Reminders that are more than half an hour late are skipped instead.
    """
    await session.execute(
        text(
            "UPDATE reminders SET state = 'skipped' "
            "WHERE platform = :platform AND state = 'scheduled' "
            "AND due_at < CAST(:now AS timestamptz) - make_interval(mins => :stale)"
        ),
        {"platform": platform, "now": now, "stale": STALE_AFTER_MIN},
    )
    result = await session.execute(
        text(
            """
            WITH due AS (
                SELECT chat_id, platform, contest_id, offset_min
                FROM reminders
                WHERE platform = :platform AND state = 'scheduled' AND due_at <= CAST(:now AS timestamptz)
                ORDER BY due_at
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            )
            UPDATE reminders r
            SET state = 'sent', sent_at = CAST(:now AS timestamptz), attempts = r.attempts + 1
            FROM due
            WHERE r.chat_id = due.chat_id AND r.platform = due.platform
              AND r.contest_id = due.contest_id AND r.offset_min = due.offset_min
            RETURNING r.chat_id, r.contest_id, r.offset_min, r.attempts, r.due_at
            """
        ),
        {"platform": platform, "now": now, "limit": limit},
    )
    return [ClaimedReminder(int(r[0]), int(r[1]), int(r[2]), int(r[3]), r[4]) for r in result.all()]


async def release_reminder(session: AsyncSession, platform: str, claimed: ClaimedReminder) -> None:
    """Put a reminder back after a send that surely did not happen (flood control, network)."""
    await session.execute(
        text(
            "UPDATE reminders SET state = 'scheduled', sent_at = NULL "
            "WHERE chat_id = :chat AND platform = :platform AND contest_id = :cid "
            "AND offset_min = :off AND state = 'sent'"
        ),
        {
            "chat": claimed.chat_id,
            "platform": platform,
            "cid": claimed.contest_id,
            "off": claimed.offset_min,
        },
    )


# --- alerts: snapshots, events, outbox --------------------------------------------------

type Snapshot = list[tuple[str, int, int | None]]  # per problem: (status, rejected, time_s)


async def load_snapshots(
    session: AsyncSession, platform: str, contest_id: int, handle_keys: Sequence[str]
) -> dict[str, Snapshot]:
    """The last stored problem results of the given handles in one contest."""
    if not handle_keys:
        return {}
    result = await session.execute(
        select(participant_results.c.handle_key, participant_results.c.problem_results).where(
            participant_results.c.platform == platform,
            participant_results.c.contest_id == contest_id,
            participant_results.c.handle_key.in_(list(handle_keys)),
        )
    )
    return {
        str(key): [(str(p[0]), int(p[1]), p[2] if p[2] is None else int(p[2])) for p in problems]
        for key, problems in result.all()
    }


async def contest_has_snapshots(session: AsyncSession, platform: str, contest_id: int) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(participant_results)
        .where(
            participant_results.c.platform == platform,
            participant_results.c.contest_id == contest_id,
        )
    )
    return int(result.scalar_one()) > 0


async def save_snapshot(
    session: AsyncSession,
    platform: str,
    contest_id: int,
    handle_key: str,
    *,
    rank: int,
    points: float,
    penalty: int,
    official: bool,
    problems: Snapshot,
) -> None:
    statement = insert(participant_results).values(
        platform=platform,
        contest_id=contest_id,
        handle_key=handle_key,
        rank=rank,
        points=points,
        penalty=penalty,
        problem_results=[list(p) for p in problems],
        official=official,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["platform", "contest_id", "handle_key"],
            set_={
                "rank": rank,
                "points": points,
                "penalty": penalty,
                "problem_results": [list(p) for p in problems],
                "official": official,
                "updated_at": func.now(),
            },
        )
    )


async def insert_solve_event(
    session: AsyncSession,
    *,
    event_key: str,
    platform: str,
    contest_id: int,
    handle_key: str,
    problem: str,
    kind: str,
    occurred_at: datetime,
) -> bool:
    """Record a fact once; returns False when it was already known (a replayed poll)."""
    result = await session.execute(
        insert(solve_events)
        .values(
            event_key=event_key,
            platform=platform,
            contest_id=contest_id,
            handle_key=handle_key,
            problem=problem,
            kind=kind,
            occurred_at=occurred_at,
        )
        .on_conflict_do_nothing()
        .returning(solve_events.c.event_key)
    )
    return result.first() is not None


async def watchers_of(
    session: AsyncSession, platform: str, handle_keys: Sequence[str], kind: str = "solve"
) -> dict[str, list[int]]:
    """Active chats with alerts on that follow each handle and want this kind of alert."""
    if not handle_keys:
        return {}
    field = getattr(watched_handles.c, KIND_FIELD[kind])
    result = await session.execute(
        select(watched_handles.c.handle_key, watched_handles.c.chat_id)
        .join(chats, chats.c.chat_id == watched_handles.c.chat_id)
        .where(
            watched_handles.c.platform == platform,
            watched_handles.c.handle_key.in_(list(handle_keys)),
            chats.c.status == "active",
            chats.c.alerts_enabled.is_(True),
            field.is_(True),
        )
    )
    found: dict[str, list[int]] = {}
    for key, chat_id in result.all():
        found.setdefault(str(key), []).append(int(chat_id))
    return found


async def enqueue_alert(
    session: AsyncSession,
    chat_id: int,
    event_key: str,
    payload: dict[str, object],
    *,
    not_before: datetime,
) -> bool:
    """Put an alert in the outbox; a chat is told about an event at most once."""
    result = await session.execute(
        insert(deliveries)
        .values(
            chat_id=chat_id,
            kind="alert",
            event_key=event_key,
            payload=payload,
            state="pending",
            not_before=not_before,
        )
        .on_conflict_do_nothing(index_elements=["chat_id", "event_key"])
        .returning(deliveries.c.id)
    )
    return result.first() is not None


@dataclass(frozen=True, slots=True)
class ClaimedAlert:
    id: int
    chat_id: int
    event_key: str
    payload: dict[str, object]
    attempts: int


async def claim_due_alerts(
    session: AsyncSession, *, now: datetime, limit: int
) -> list[ClaimedAlert]:
    """Take due alerts and mark them sent *before* sending: at most once per chat and event."""
    result = await session.execute(
        text(
            """
            WITH due AS (
                SELECT id FROM deliveries
                WHERE kind = 'alert' AND state = 'pending' AND not_before <= CAST(:now AS timestamptz)
                ORDER BY not_before, id
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            )
            UPDATE deliveries d
            SET state = 'sent', attempts = d.attempts + 1
            FROM due
            WHERE d.id = due.id
            RETURNING d.id, d.chat_id, d.event_key, d.payload, d.attempts
            """
        ),
        {"now": now, "limit": limit},
    )
    return [
        ClaimedAlert(int(r[0]), int(r[1]), str(r[2]), dict(r[3]), int(r[4])) for r in result.all()
    ]


async def release_alerts(
    session: AsyncSession, alerts: Sequence[ClaimedAlert], *, not_before: datetime, error: str
) -> None:
    """Put alerts back after a send that surely did not happen."""
    await session.execute(
        update(deliveries)
        .where(deliveries.c.id.in_([a.id for a in alerts]), deliveries.c.state == "sent")
        .values(state="pending", not_before=not_before, last_error=error[:200])
    )


async def fail_alerts(session: AsyncSession, alerts: Sequence[ClaimedAlert], *, error: str) -> None:
    await session.execute(
        update(deliveries)
        .where(deliveries.c.id.in_([a.id for a in alerts]))
        .values(state="failed", last_error=error[:200])
    )


async def active_contests_to_watch(session: AsyncSession, platform: str) -> list[int]:
    """Running contests that at least one chat with alerts on is waiting for."""
    result = await session.execute(
        text(
            """
            SELECT c.external_id FROM contests c
            WHERE c.platform = :platform
              AND c.phase IN ('CODING', 'PENDING_SYSTEM_TEST', 'SYSTEM_TEST')
              AND EXISTS (
                SELECT 1 FROM watched_handles w JOIN chats ch ON ch.chat_id = w.chat_id
                WHERE w.platform = c.platform AND ch.status = 'active' AND ch.alerts_enabled
              )
            ORDER BY c.external_id
            """
        ),
        {"platform": platform},
    )
    return [int(row[0]) for row in result.all()]


async def watched_keys_of_active_chats(session: AsyncSession, platform: str) -> set[str]:
    """Handles somebody wants alerts for (a solve or a system-test alert)."""
    result = await session.execute(
        select(watched_handles.c.handle_key)
        .join(chats, chats.c.chat_id == watched_handles.c.chat_id)
        .where(
            watched_handles.c.platform == platform,
            chats.c.status == "active",
            chats.c.alerts_enabled.is_(True),
            or_(
                watched_handles.c.notify_solve.is_(True), watched_handles.c.notify_systest.is_(True)
            ),
        )
        .distinct()
    )
    return {str(row[0]) for row in result.all()}


async def set_alerts_enabled(session: AsyncSession, chat_id: int, enabled: bool) -> bool:
    ok = await _update_chat(session, chat_id, alerts_enabled=enabled)
    if ok and not enabled:
        await session.execute(
            text(
                "UPDATE deliveries SET state = 'failed', last_error = 'alerts switched off' "
                "WHERE chat_id = :chat AND kind = 'alert' AND state = 'pending' "
                "AND COALESCE(payload->>'kind', '') <> 'summary'"
            ),
            {"chat": chat_id},
        )
    return ok


# --- notification levels and per-friend toggles -----------------------------------------

LEVEL_TOGGLES: dict[int, dict[str, bool]] = {
    0: {"show_in_list": False, "notify_solve": False, "notify_systest": False, "notify_upsolve": False},
    1: {"show_in_list": True, "notify_solve": False, "notify_systest": False, "notify_upsolve": False},
    2: {"show_in_list": True, "notify_solve": False, "notify_systest": True, "notify_upsolve": False},
    3: {"show_in_list": True, "notify_solve": False, "notify_systest": True, "notify_upsolve": True},
    4: {"show_in_list": True, "notify_solve": True, "notify_systest": True, "notify_upsolve": True},
}  # fmt: skip
TOGGLE_FIELDS = ("show_in_list", "notify_solve", "notify_systest", "notify_upsolve")
KIND_FIELD = {
    "solve": "notify_solve",
    "systest_fail": "notify_systest",
    "upsolve": "notify_upsolve",
}


@dataclass(frozen=True, slots=True)
class Friend:
    key: str
    display: str
    show_in_list: bool
    notify_solve: bool
    notify_systest: bool
    notify_upsolve: bool

    def toggle(self, field: str) -> bool:
        return bool(getattr(self, field))


async def set_notify_level(session: AsyncSession, chat_id: int, level: int) -> bool:
    """Set the chat's level and apply it to every followed handle (overrides come after)."""
    if level not in LEVEL_TOGGLES:
        raise ValueError(f"unknown notification level {level}")
    ok = await _update_chat(session, chat_id, notify_level=level)
    if ok:
        await session.execute(
            update(watched_handles)
            .where(watched_handles.c.chat_id == chat_id)
            .values(**LEVEL_TOGGLES[level])
        )
    return ok


async def list_friends(session: AsyncSession, chat_id: int, platform: str) -> list[Friend]:
    result = await session.execute(
        select(
            watched_handles.c.handle_key,
            watched_handles.c.handle_display,
            watched_handles.c.show_in_list,
            watched_handles.c.notify_solve,
            watched_handles.c.notify_systest,
            watched_handles.c.notify_upsolve,
        )
        .where(watched_handles.c.chat_id == chat_id, watched_handles.c.platform == platform)
        .order_by(watched_handles.c.handle_key)
    )
    return [
        Friend(str(k), str(d), bool(a), bool(b), bool(c), bool(e))
        for k, d, a, b, c, e in result.all()
    ]


async def get_friend(session: AsyncSession, chat_id: int, platform: str, key: str) -> Friend | None:
    for friend in await list_friends(session, chat_id, platform):
        if friend.key == key:
            return friend
    return None


async def set_friend_toggle(
    session: AsyncSession, chat_id: int, platform: str, key: str, field: str, value: bool
) -> bool:
    if field not in TOGGLE_FIELDS:
        raise ValueError(f"unknown toggle {field}")
    result = await session.execute(
        update(watched_handles)
        .where(
            watched_handles.c.chat_id == chat_id,
            watched_handles.c.platform == platform,
            watched_handles.c.handle_key == key,
        )
        .values(**{field: value})
        .returning(watched_handles.c.handle_key)
    )
    return result.first() is not None


async def scoreboard_keys(session: AsyncSession, chat_id: int, platform: str) -> set[str]:
    """Handles shown in the friends view of this chat's standings."""
    result = await session.execute(
        select(watched_handles.c.handle_key).where(
            watched_handles.c.chat_id == chat_id,
            watched_handles.c.platform == platform,
            watched_handles.c.show_in_list.is_(True),
        )
    )
    return {str(row[0]) for row in result.all()}


async def summary_audience(session: AsyncSession, platform: str) -> dict[int, dict[str, str]]:
    """Active chats that want post-contest summaries -> {handle key: display} they follow."""
    result = await session.execute(
        select(
            watched_handles.c.chat_id,
            watched_handles.c.handle_key,
            watched_handles.c.handle_display,
        )
        .join(chats, chats.c.chat_id == watched_handles.c.chat_id)
        .where(
            watched_handles.c.platform == platform,
            watched_handles.c.show_in_list.is_(True),
            chats.c.status == "active",
            chats.c.summary_enabled.is_(True),
        )
    )
    audience: dict[int, dict[str, str]] = {}
    for chat_id, key, display in result.all():
        audience.setdefault(int(chat_id), {})[str(key)] = str(display)
    return audience


async def upsolve_targets(session: AsyncSession, platform: str) -> dict[str, str]:
    """Handles somebody wants upsolve alerts for -> display spelling."""
    result = await session.execute(
        select(watched_handles.c.handle_key, func.min(watched_handles.c.handle_display))
        .join(chats, chats.c.chat_id == watched_handles.c.chat_id)
        .where(
            watched_handles.c.platform == platform,
            watched_handles.c.notify_upsolve.is_(True),
            chats.c.status == "active",
            chats.c.alerts_enabled.is_(True),
        )
        .group_by(watched_handles.c.handle_key)
    )
    return {str(key): str(display) for key, display in result.all()}


async def upsolve_watchers(
    session: AsyncSession, platform: str, key: str, at: datetime
) -> list[int]:
    """Chats that wanted upsolve alerts for ``key`` already when the solve happened."""
    result = await session.execute(
        select(watched_handles.c.chat_id)
        .join(chats, chats.c.chat_id == watched_handles.c.chat_id)
        .where(
            watched_handles.c.platform == platform,
            watched_handles.c.handle_key == key,
            watched_handles.c.notify_upsolve.is_(True),
            watched_handles.c.added_at <= at,
            chats.c.status == "active",
            chats.c.alerts_enabled.is_(True),
        )
    )
    return [int(row[0]) for row in result.all()]
