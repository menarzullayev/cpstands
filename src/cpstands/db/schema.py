"""SQLAlchemy Core description of the R1 schema.

This is the single Python-side description of the tables in the technical specification (stage 08).
Migrations are written explicitly; a test checks that the migrated database matches this metadata.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP

metadata = MetaData()


def _ts(name: str, *, nullable: bool = True, default_now: bool = False) -> Column[object]:
    return Column(
        name,
        TIMESTAMP(timezone=True),
        nullable=nullable,
        server_default=text("now()") if default_now else None,
    )


chats = Table(
    "chats",
    metadata,
    Column("chat_id", BigInteger, primary_key=True, autoincrement=False),
    Column("chat_type", Text, nullable=False),
    Column("language", Text),
    Column("time_zone", Text),
    Column("tone", Text, nullable=False, server_default="playful"),
    Column("alerts_enabled", Boolean, nullable=False, server_default=text("true")),
    Column(
        "reminder_offsets",
        ARRAY(Integer),
        nullable=False,
        server_default=text("'{1440,60,10}'::integer[]"),
    ),
    Column("status", Text, nullable=False, server_default="onboarding"),
    Column("notify_level", Integer, nullable=False, server_default=text("4")),
    Column("table_cols", Integer, nullable=False, server_default=text("16")),
    Column("summary_enabled", Boolean, nullable=False, server_default=text("true")),
    _ts("created_at", nullable=False, default_now=True),
    _ts("updated_at", nullable=False, default_now=True),
    CheckConstraint(
        "chat_type IN ('private','group','supergroup','channel')", name="chats_chat_type_check"
    ),
    CheckConstraint("language IN ('uz','ru','en')", name="chats_language_check"),
    CheckConstraint("tone IN ('playful','neutral')", name="chats_tone_check"),
    CheckConstraint(
        "status IN ('onboarding','active','paused','removed','deleted')", name="chats_status_check"
    ),
    CheckConstraint("notify_level BETWEEN 0 AND 4", name="chats_notify_level_check"),
    CheckConstraint("table_cols IN (8, 12, 16)", name="chats_table_cols_check"),
)

watched_handles = Table(
    "watched_handles",
    metadata,
    Column(
        "chat_id", BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("platform", Text, primary_key=True),
    Column("handle_key", Text, primary_key=True),
    Column("handle_display", Text, nullable=False),
    Column("show_in_list", Boolean, nullable=False, server_default=text("true")),
    Column("notify_solve", Boolean, nullable=False, server_default=text("true")),
    Column("notify_systest", Boolean, nullable=False, server_default=text("true")),
    Column("notify_upsolve", Boolean, nullable=False, server_default=text("true")),
    _ts("added_at", nullable=False, default_now=True),
)

contests = Table(
    "contests",
    metadata,
    Column("platform", Text, primary_key=True),
    Column("external_id", BigInteger, primary_key=True, autoincrement=False),
    Column("name", Text, nullable=False),
    Column("phase", Text, nullable=False),
    _ts("starts_at"),
    Column("duration_s", Integer),
    Column("problems", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("source_version", BigInteger, nullable=False, server_default=text("0")),
    _ts("updated_at", nullable=False, default_now=True),
)

participant_results = Table(
    "participant_results",
    metadata,
    Column("platform", Text, primary_key=True),
    Column("contest_id", BigInteger, primary_key=True, autoincrement=False),
    Column("handle_key", Text, primary_key=True),
    Column("rank", Integer),
    Column("points", Numeric),
    Column("penalty", Integer),
    Column("problem_results", JSONB, nullable=False),
    Column("official", Boolean, nullable=False),
    _ts("updated_at", nullable=False, default_now=True),
)

solve_events = Table(
    "solve_events",
    metadata,
    Column("event_key", Text, primary_key=True),
    Column("platform", Text, nullable=False),
    Column("contest_id", BigInteger, nullable=False),
    Column("handle_key", Text, nullable=False),
    Column("problem", Text, nullable=False),
    Column("kind", Text, nullable=False),
    _ts("occurred_at", nullable=False),
    _ts("created_at", nullable=False, default_now=True),
    CheckConstraint(
        "kind IN ('solve','upsolve','systest_fail','systest_pass')", name="solve_events_kind_check"
    ),
)

reminders = Table(
    "reminders",
    metadata,
    Column(
        "chat_id", BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("platform", Text, primary_key=True),
    Column("contest_id", BigInteger, primary_key=True, autoincrement=False),
    Column("offset_min", Integer, primary_key=True, autoincrement=False),
    _ts("due_at", nullable=False),
    Column("state", Text, nullable=False, server_default="scheduled"),
    _ts("sent_at"),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    CheckConstraint(
        "state IN ('scheduled','sent','cancelled','skipped')", name="reminders_state_check"
    ),
)

standings_messages = Table(
    "standings_messages",
    metadata,
    Column(
        "chat_id", BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("platform", Text, primary_key=True),
    Column("contest_id", BigInteger, primary_key=True, autoincrement=False),
    Column("message_id", BigInteger),
    Column("state", Text, nullable=False, server_default="active"),
    Column("last_hash", Text),
    _ts("last_edit_at"),
    Column("dirty", Boolean, nullable=False, server_default=text("false")),
    Column("row_page", Integer, nullable=False, server_default=text("0")),
    Column("col_page", Integer, nullable=False, server_default=text("0")),
    Column("view", Text, nullable=False, server_default="auto"),
    CheckConstraint(
        "state IN ('active','frozen','orphaned')", name="standings_messages_state_check"
    ),
    CheckConstraint("view IN ('auto', 'friends', 'all')", name="standings_messages_view_check"),
)

deliveries = Table(
    "deliveries",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("chat_id", BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("event_key", Text),
    Column("payload", JSONB, nullable=False),
    Column("state", Text, nullable=False, server_default="pending"),
    _ts("not_before", nullable=False, default_now=True),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("last_error", Text),
    CheckConstraint("kind IN ('alert','reminder','standings')", name="deliveries_kind_check"),
    CheckConstraint(
        "state IN ('pending','batched','sent','failed')", name="deliveries_state_check"
    ),
    UniqueConstraint("chat_id", "event_key", name="deliveries_chat_event_key"),
    Index(
        "deliveries_due",
        "not_before",
        postgresql_where=text("state IN ('pending','batched')"),
    ),
)

source_health = Table(
    "source_health",
    metadata,
    Column("source", Text, primary_key=True),
    _ts("last_success_at"),
    Column("consecutive_errors", Integer, nullable=False, server_default=text("0")),
    Column("paused", Boolean, nullable=False, server_default=text("false")),
    Column("note", Text),
)

deletion_requests = Table(
    "deletion_requests",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("subject_type", Text, nullable=False),
    Column("subject_id", BigInteger, nullable=False),
    _ts("requested_at", nullable=False, default_now=True),
    _ts("completed_at"),
)

runtime_state = Table(
    "runtime_state",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", JSONB, nullable=False),
)
