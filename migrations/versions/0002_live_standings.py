"""remember which page of a live standings message the reader is looking at

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08 12:00:00+00:00

A live standings message is edited in place while the contest runs; the edit must keep the
row page and the problem-column page the reader chose.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("row_page", "col_page"):
        op.add_column(
            "standings_messages",
            sa.Column(column, sa.Integer(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    op.drop_column("standings_messages", "col_page")
    op.drop_column("standings_messages", "row_page")
