"""baseline R1 schema

Revision ID: 0001
Revises:
Create Date: 2026-11-08 00:00:00+00:00

Creates the tables of the technical specification (stage 08). Constraints carry the domain
invariants: one standings message per chat and contest, one reminder per offset, deterministic
event keys, and at most one delivery per chat and event.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str, *, nullable: bool = True, now: bool = False) -> sa.Column[object]:
    return sa.Column(
        name,
        postgresql.TIMESTAMP(timezone=True),
        nullable=nullable,
        server_default=sa.text("now()") if now else None,
    )


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("chat_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("chat_type", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("time_zone", sa.Text(), nullable=True),
        sa.Column("tone", sa.Text(), server_default="playful", nullable=False),
        sa.Column("alerts_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "reminder_offsets",
            postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("'{1440,60,10}'::integer[]"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="onboarding", nullable=False),
        _ts("created_at", nullable=False, now=True),
        _ts("updated_at", nullable=False, now=True),
        sa.CheckConstraint(
            "chat_type IN ('private','group','supergroup')", name="chats_chat_type_check"
        ),
        sa.CheckConstraint("language IN ('uz','ru','en')", name="chats_language_check"),
        sa.CheckConstraint("tone IN ('playful','neutral')", name="chats_tone_check"),
        sa.CheckConstraint(
            "status IN ('onboarding','active','paused','removed','deleted')",
            name="chats_status_check",
        ),
        sa.PrimaryKeyConstraint("chat_id"),
    )
    op.create_table(
        "watched_handles",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("handle_key", sa.Text(), nullable=False),
        sa.Column("handle_display", sa.Text(), nullable=False),
        _ts("added_at", nullable=False, now=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_id", "platform", "handle_key"),
    )
    op.create_table(
        "contests",
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        _ts("starts_at"),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column(
            "problems", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("source_version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        _ts("updated_at", nullable=False, now=True),
        sa.PrimaryKeyConstraint("platform", "external_id"),
    )
    op.create_table(
        "participant_results",
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("handle_key", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("points", sa.Numeric(), nullable=True),
        sa.Column("penalty", sa.Integer(), nullable=True),
        sa.Column("problem_results", postgresql.JSONB(), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False),
        _ts("updated_at", nullable=False, now=True),
        sa.PrimaryKeyConstraint("platform", "contest_id", "handle_key"),
    )
    op.create_table(
        "solve_events",
        sa.Column("event_key", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("handle_key", sa.Text(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        _ts("occurred_at", nullable=False),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            "kind IN ('solve','upsolve','systest_fail','systest_pass')",
            name="solve_events_kind_check",
        ),
        sa.PrimaryKeyConstraint("event_key"),
    )
    op.create_table(
        "reminders",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("offset_min", sa.Integer(), autoincrement=False, nullable=False),
        _ts("due_at", nullable=False),
        sa.Column("state", sa.Text(), server_default="scheduled", nullable=False),
        _ts("sent_at"),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "state IN ('scheduled','sent','cancelled','skipped')", name="reminders_state_check"
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_id", "platform", "contest_id", "offset_min"),
    )
    op.create_table(
        "standings_messages",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column("last_hash", sa.Text(), nullable=True),
        _ts("last_edit_at"),
        sa.Column("dirty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "state IN ('active','frozen','orphaned')", name="standings_messages_state_check"
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_id", "platform", "contest_id"),
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("event_key", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.Text(), server_default="pending", nullable=False),
        _ts("not_before", nullable=False, now=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('alert','reminder','standings')", name="deliveries_kind_check"
        ),
        sa.CheckConstraint(
            "state IN ('pending','batched','sent','failed')", name="deliveries_state_check"
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "event_key", name="deliveries_chat_event_key"),
    )
    op.create_index(
        "deliveries_due",
        "deliveries",
        ["not_before"],
        postgresql_where=sa.text("state IN ('pending','batched')"),
    )
    op.create_table(
        "source_health",
        sa.Column("source", sa.Text(), nullable=False),
        _ts("last_success_at"),
        sa.Column("consecutive_errors", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("source"),
    )
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=False),
        _ts("requested_at", nullable=False, now=True),
        _ts("completed_at"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "runtime_state",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("runtime_state")
    op.drop_table("deletion_requests")
    op.drop_table("source_health")
    op.drop_index("deliveries_due", table_name="deliveries")
    op.drop_table("deliveries")
    op.drop_table("standings_messages")
    op.drop_table("reminders")
    op.drop_table("solve_events")
    op.drop_table("participant_results")
    op.drop_table("contests")
    op.drop_table("watched_handles")
    op.drop_table("chats")
