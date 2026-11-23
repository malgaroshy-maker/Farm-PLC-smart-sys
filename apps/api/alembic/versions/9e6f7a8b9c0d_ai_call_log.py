"""ai_call_log table for the AI usage view (Milestone G2)

Revision ID: 9e6f7a8b9c0d
Revises: 8d5e6f7a8b9c
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e6f7a8b9c0d"
down_revision: str | None = "8d5e6f7a8b9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("fallback_reason", sa.String(200)),
        sa.Column("requests", sa.Integer(), server_default="0"),
        sa.Column("input_tokens", sa.Integer(), server_default="0"),
        sa.Column("output_tokens", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_ai_call_log_ts", "ai_call_log", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_ai_call_log_ts", table_name="ai_call_log")
    op.drop_table("ai_call_log")
