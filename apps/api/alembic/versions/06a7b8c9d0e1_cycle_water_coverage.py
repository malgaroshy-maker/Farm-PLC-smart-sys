"""Track missing flow coverage in irrigation cycle volumes."""

import sqlalchemy as sa

from alembic import op

revision = "06a7b8c9d0e1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "irrigation_cycles",
        sa.Column("water_has_gaps", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("irrigation_cycles", "water_has_gaps")
