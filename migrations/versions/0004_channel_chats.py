"""allow channel chats (reminders posted to the project channel)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08 21:00:00+00:00

Owner decision 2026-11-08: the project channel gets automatic contest reminders. A channel is
stored as an ordinary chat row with chat_type 'channel'.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("chats_chat_type_check", "chats", type_="check")
    op.create_check_constraint(
        "chats_chat_type_check", "chats", "chat_type IN ('private','group','supergroup','channel')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM chats WHERE chat_type = 'channel'")
    op.drop_constraint("chats_chat_type_check", "chats", type_="check")
    op.create_check_constraint(
        "chats_chat_type_check", "chats", "chat_type IN ('private','group','supergroup')"
    )
