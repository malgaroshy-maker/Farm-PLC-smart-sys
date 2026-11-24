"""soil moisture levels per crop, per-zone overrides and soil limits, external soil probes (G7)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Proposed starting levels (% of available water). Not confirmed: the owner reviews them
# in Settings first, and soil logic stays off for a crop until its levels are confirmed.
PROPOSED = [
    ("olives", 40.0, 85.0),
    ("pomegranate", 50.0, 90.0),
    ("grapes", 45.0, 85.0),
    ("mixed_fruit", 55.0, 90.0),
    ("other", 50.0, 90.0),
]


def upgrade() -> None:
    levels = op.create_table(
        "crop_moisture_levels",
        sa.Column("crop_type", sa.String(30), primary_key=True),
        sa.Column("start_pct", sa.Float(), nullable=False),
        sa.Column("stop_pct", sa.Float(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.String(64)),
    )
    op.bulk_insert(
        levels,
        [{"crop_type": c, "start_pct": a, "stop_pct": b, "confirmed": False} for c, a, b in PROPOSED],
    )
    with op.batch_alter_table("zones") as b:
        b.add_column(sa.Column("moisture_start_pct", sa.Float()))
        b.add_column(sa.Column("moisture_stop_pct", sa.Float()))
        b.add_column(sa.Column("soil_fc_vwc", sa.Float()))
        b.add_column(sa.Column("soil_wp_vwc", sa.Float()))
    with op.batch_alter_table("sensors") as b:
        b.add_column(sa.Column("external_id", sa.String(64)))
        b.add_column(sa.Column("depth_cm", sa.Integer()))
        b.create_index("ix_sensors_external_id", ["external_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("sensors") as b:
        b.drop_index("ix_sensors_external_id")
        b.drop_column("depth_cm")
        b.drop_column("external_id")
    with op.batch_alter_table("zones") as b:
        b.drop_column("soil_wp_vwc")
        b.drop_column("soil_fc_vwc")
        b.drop_column("moisture_stop_pct")
        b.drop_column("moisture_start_pct")
    op.drop_table("crop_moisture_levels")
