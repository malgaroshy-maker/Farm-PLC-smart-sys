"""Update default AI models to DeepSeek v4 Pro and Muse Spark.

Revision ID: 7c4d5e6f7a8b
Revises: 6b3c4d5e6f7a
Create Date: 2026-11-19 21:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c4d5e6f7a8b"
down_revision: str | None = "6b3c4d5e6f7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Update existing default settings rows if present
    op.execute(
        sa.text(
            """
            UPDATE ai_settings
            SET apinex_model = 'free/deepseek-v4-pro-0813',
                apinex_fallback_model = 'free/muse-spark-1.3',
                gemini_model = 'gemini-2.5-flash'
            WHERE id = 'default'
               OR apinex_model = 'free/gemini-3.8-flash'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE ai_settings
            SET apinex_model = 'free/gemini-3.8-flash',
                apinex_fallback_model = 'free/glm-5.3-flash',
                gemini_model = 'gemini-2.5-flash'
            WHERE id = 'default'
               OR apinex_model = 'free/deepseek-v4-pro-0813'
            """
        )
    )
