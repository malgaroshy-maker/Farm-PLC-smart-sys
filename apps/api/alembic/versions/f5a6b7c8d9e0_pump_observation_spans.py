"""Persist observed pump feedback for runtime and start reporting."""

import sqlalchemy as sa

from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pump_observation_spans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pump_id", sa.String(64), sa.ForeignKey("pumps.id"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("timeline", sa.String(40), nullable=False),
        sa.Column("running", sa.Boolean(), nullable=True),
        sa.Column("start_observed", sa.Boolean(), nullable=False),
        sa.Column("observed_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sample_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_pump_observation_report",
        "pump_observation_spans",
        ["pump_id", "source", "observed_from"],
    )
    op.create_index("ix_pump_observation_latest", "pump_observation_spans", ["pump_id", "id"])


def downgrade() -> None:
    op.drop_table("pump_observation_spans")
