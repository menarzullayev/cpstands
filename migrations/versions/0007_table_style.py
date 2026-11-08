"""standings table style per chat: emoji (default) or classic

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08 09:00:00+00:00

Owner decision 2026-11-08: tables mark solved problems with emoji by default; a chat can switch
to the classic look (stripes, highlighted first solves) in /settings.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("table_style", sa.Text(), nullable=False, server_default=sa.text("'emoji'")),
    )
    op.create_check_constraint(
        "chats_table_style_check", "chats", "table_style IN ('emoji', 'classic')"
    )


def downgrade() -> None:
    op.drop_constraint("chats_table_style_check", "chats", type_="check")
    op.drop_column("chats", "table_style")
