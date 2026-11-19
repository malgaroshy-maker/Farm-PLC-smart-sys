"""Add water_is_estimate to irrigation_cycles.

Revision ID: 4e1f8d2a3c5b
Revises: 3d9f8e2a1b4c
Create Date: 2026-11-19 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4e1f8d2a3c5b"
down_revision: str | None = "3d9f8e2a1b4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("irrigation_cycles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "water_is_estimate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("irrigation_cycles") as batch_op:
        batch_op.drop_column("water_is_estimate")
