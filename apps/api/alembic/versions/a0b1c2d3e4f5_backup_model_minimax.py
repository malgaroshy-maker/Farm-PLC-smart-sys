"""Backup AI model: muse-spark-1.3 became subscription-only (402); use minimax-m3.1-flash

Owner asked to test the models and select (2026-11-23). Only rows still on the old
default are changed.

Revision ID: a0b1c2d3e4f5
Revises: 9e6f7a8b9c0d
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "9e6f7a8b9c0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE ai_settings SET apinex_fallback_model = 'free/minimax-m3.1-flash' "
        "WHERE apinex_fallback_model = 'free/muse-spark-1.3'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE ai_settings SET apinex_fallback_model = 'free/muse-spark-1.3' "
        "WHERE apinex_fallback_model = 'free/minimax-m3.1-flash'"
    )
