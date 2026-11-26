"""Align nullable AI usage and push failure counters with the models."""

import sqlalchemy as sa

from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

COUNTERS = {
    "ai_call_log": ("requests", "input_tokens", "output_tokens"),
    "push_subscriptions": ("failures",),
}


def upgrade() -> None:
    for name, columns in COUNTERS.items():
        table = sa.table(name, *(sa.column(column, sa.Integer()) for column in columns))
        for column in table.c:
            op.execute(table.update().where(column.is_(None)).values({column.key: 0}))
        with op.batch_alter_table(name) as batch:
            for column in columns:
                batch.alter_column(column, existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for name, columns in COUNTERS.items():
        with op.batch_alter_table(name) as batch:
            for column in columns:
                batch.alter_column(column, existing_type=sa.Integer(), nullable=True)
