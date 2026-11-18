"""Add farm_clock table and commands.requested_at_real column.

Revision ID: 2c8a7d3b5e1f
Revises: 1eba5b0fdbf6
Create Date: 2026-11-19 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2c8a7d3b5e1f"
down_revision: str | None = "1eba5b0fdbf6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "farm_clock",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default="real"),
        sa.Column("speed", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("anchor_real", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_sim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "commands",
        sa.Column("requested_at_real", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("commands", "requested_at_real")
    op.drop_table("farm_clock")
