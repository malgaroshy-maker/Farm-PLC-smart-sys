"""users.token_version: signing a user out everywhere

Revision ID: 17b8c9d0e1f2
Revises: 06a7b8c9d0e1
"""

import sqlalchemy as sa

from alembic import op

revision = "17b8c9d0e1f2"
down_revision = "06a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
