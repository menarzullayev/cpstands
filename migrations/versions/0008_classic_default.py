"""the classic standings table becomes the default style

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08 09:45:00+00:00

Owner decision 2026-11-08: the striped classic table is the default. The style setting was an
hour old and no chat had picked a style yet (all 6 had the old default), so every chat moves.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("chats", "table_style", server_default=sa.text("'classic'"))
    op.execute("UPDATE chats SET table_style = 'classic' WHERE table_style = 'emoji'")


def downgrade() -> None:
    op.alter_column("chats", "table_style", server_default=sa.text("'emoji'"))
