"""per-chat and per-friend notification settings, table width, summary switch, standings view

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08 18:00:00+00:00

Upstream-parity features chosen by the owner: notification level 0-4 per chat with four
per-handle toggles, table width, a post-contest summary switch, and the friends/all view of a
live standings message.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HANDLE_TOGGLES = ("show_in_list", "notify_solve", "notify_systest", "notify_upsolve")


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("notify_level", sa.Integer(), nullable=False, server_default=sa.text("4")),
    )
    op.add_column(
        "chats", sa.Column("table_cols", sa.Integer(), nullable=False, server_default=sa.text("16"))
    )
    op.add_column(
        "chats",
        sa.Column("summary_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_check_constraint("chats_notify_level_check", "chats", "notify_level BETWEEN 0 AND 4")
    op.create_check_constraint("chats_table_cols_check", "chats", "table_cols IN (8, 12, 16)")
    for name in HANDLE_TOGGLES:
        op.add_column(
            "watched_handles",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
    op.add_column(
        "standings_messages",
        sa.Column("view", sa.Text(), nullable=False, server_default="auto"),
    )
    op.create_check_constraint(
        "standings_messages_view_check", "standings_messages", "view IN ('auto', 'friends', 'all')"
    )


def downgrade() -> None:
    op.drop_constraint("standings_messages_view_check", "standings_messages", type_="check")
    op.drop_column("standings_messages", "view")
    for name in reversed(HANDLE_TOGGLES):
        op.drop_column("watched_handles", name)
    op.drop_constraint("chats_table_cols_check", "chats", type_="check")
    op.drop_constraint("chats_notify_level_check", "chats", type_="check")
    op.drop_column("chats", "summary_enabled")
    op.drop_column("chats", "table_cols")
    op.drop_column("chats", "notify_level")
