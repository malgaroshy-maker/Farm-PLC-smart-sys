"""notification_settings + push_subscriptions (Milestone G3)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("telegram_chat_id", sa.String(40)),
        sa.Column("vapid_public_key", sa.Text()),
        sa.Column("vapid_private_key", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64)),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ok_at", sa.DateTime(timezone=True)),
        sa.Column("failures", sa.Integer(), server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    op.drop_table("notification_settings")
