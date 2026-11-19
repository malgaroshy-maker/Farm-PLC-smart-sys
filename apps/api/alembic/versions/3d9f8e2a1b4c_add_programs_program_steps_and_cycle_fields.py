"""Add programs, program_steps, scheduler_state tables and irrigation_cycle fields.

Revision ID: 3d9f8e2a1b4c
Revises: 2c8a7d3b5e1f
Create Date: 2026-11-19 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3d9f8e2a1b4c"
down_revision: str | None = "2c8a7d3b5e1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("start_time_local", sa.String(length=10), nullable=False),
        sa.Column(
            "weekday_mask",
            sa.String(length=30),
            nullable=False,
            server_default="1,2,3,4,5,6,7",
        ),
        sa.Column("season", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "program_steps",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "program_id",
            sa.String(length=64),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "zone_id",
            sa.String(length=64),
            sa.ForeignKey("zones.id"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "scheduler_state",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Use batch_alter_table for SQLite compatibility with explicitly named foreign keys
    with op.batch_alter_table("irrigation_cycles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "program_id",
                sa.String(length=64),
                sa.ForeignKey("programs.id", name="fk_cycles_program_id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "program_step_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "program_steps.id",
                    name="fk_cycles_program_step_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "command_id",
                sa.String(length=64),
                sa.ForeignKey("commands.id", name="fk_cycles_command_id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("alarms_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("irrigation_cycles") as batch_op:
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("alarms_json")
        batch_op.drop_column("command_id")
        batch_op.drop_column("program_step_id")
        batch_op.drop_column("program_id")
    op.drop_table("scheduler_state")
    op.drop_table("program_steps")
    op.drop_table("programs")
