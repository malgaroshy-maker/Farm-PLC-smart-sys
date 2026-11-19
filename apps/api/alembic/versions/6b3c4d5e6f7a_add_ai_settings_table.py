"""Add ai_settings table for persistent AI configuration.

Revision ID: 6b3c4d5e6f7a
Revises: 5a2b3c4d5e6f
Create Date: 2026-11-19 20:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b3c4d5e6f7a"
down_revision: str | None = "5a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("global_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("primary_provider", sa.String(length=32), nullable=False, server_default="apinex"),
        sa.Column("fallback_provider", sa.String(length=32), nullable=False, server_default="gemini"),
        sa.Column("apinex_base_url", sa.String(length=255), nullable=False, server_default="https://api.apinex.bond/v1"),
        sa.Column("apinex_model", sa.String(length=100), nullable=False, server_default="free/gemini-3.8-flash"),
        sa.Column("apinex_fallback_model", sa.String(length=100), nullable=False, server_default="free/glm-5.3-flash"),
        sa.Column("gemini_model", sa.String(length=100), nullable=False, server_default="gemini-2.5-flash"),
        sa.Column("model_alarm", sa.String(length=100), nullable=True, server_default=""),
        sa.Column("model_advisor", sa.String(length=100), nullable=True, server_default=""),
        sa.Column("model_briefing", sa.String(length=100), nullable=True, server_default=""),
        sa.Column("model_chat", sa.String(length=100), nullable=True, server_default=""),
        sa.Column("alarm_assistant_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smart_scheduling_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("predictive_maintenance_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("anomaly_detection_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weather_advisor_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("water_optimizer_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_insights_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("offline_fallback", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timeout_sec", sa.Float(), nullable=False, server_default="45.0"),
        sa.Column("advisor_timeout_sec", sa.Float(), nullable=False, server_default="90.0"),
        sa.Column("token_budget", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("daily_briefing_time", sa.String(length=10), nullable=False, server_default="06:00"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_settings")
