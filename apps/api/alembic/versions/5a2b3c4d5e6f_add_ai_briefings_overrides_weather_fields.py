"""Add AI briefings, program overrides, and weather cache fields.

Revision ID: 5a2b3c4d5e6f
Revises: 4e1f8d2a3c5b
Create Date: 2026-11-19 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5a2b3c4d5e6f"
down_revision: str | None = "4e1f8d2a3c5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add raw_payload_json and et0_mm to weather_cache
    with op.batch_alter_table("weather_cache") as batch_op:
        batch_op.add_column(sa.Column("raw_payload_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("et0_mm", sa.Float(), nullable=True))

    # 2. Create program_overrides table
    op.create_table(
        "program_overrides",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("program_id", sa.String(length=64), nullable=True),
        sa.Column("target_date", sa.String(length=10), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("duration_factor", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("suggestion_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suggestion_id"], ["ai_suggestions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("program_overrides") as batch_op:
        batch_op.create_index(batch_op.f("ix_program_overrides_target_date"), ["target_date"], unique=False)

    # 3. Create ai_briefings table
    op.create_table(
        "ai_briefings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("title_ar", sa.String(length=200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_ar", sa.Text(), nullable=True),
        sa.Column("weather_summary", sa.Text(), nullable=True),
        sa.Column("weather_summary_ar", sa.Text(), nullable=True),
        sa.Column("irrigation_overview", sa.Text(), nullable=True),
        sa.Column("irrigation_overview_ar", sa.Text(), nullable=True),
        sa.Column("alarms_overview", sa.Text(), nullable=True),
        sa.Column("alarms_overview_ar", sa.Text(), nullable=True),
        sa.Column("recommendations_json", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("provider_used", sa.String(length=30), nullable=False, server_default="rule_based"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_briefings") as batch_op:
        batch_op.create_index(batch_op.f("ix_ai_briefings_date"), ["date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_briefings") as batch_op:
        batch_op.drop_index(batch_op.f("ix_ai_briefings_date"))
    op.drop_table("ai_briefings")

    with op.batch_alter_table("program_overrides") as batch_op:
        batch_op.drop_index(batch_op.f("ix_program_overrides_target_date"))
    op.drop_table("program_overrides")

    with op.batch_alter_table("weather_cache") as batch_op:
        batch_op.drop_column("et0_mm")
        batch_op.drop_column("raw_payload_json")
