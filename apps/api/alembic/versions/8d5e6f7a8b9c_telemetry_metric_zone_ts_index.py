"""telemetry composite index (metric_key, zone_id, ts) for fast chart queries

Revision ID: 8d5e6f7a8b9c
Revises: 1b84f3124c4a
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8d5e6f7a8b9c"
down_revision: str | None = "1b84f3124c4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_telemetry_metric_zone_ts", "telemetry_points", ["metric_key", "zone_id", "ts"]
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_metric_zone_ts", table_name="telemetry_points")
