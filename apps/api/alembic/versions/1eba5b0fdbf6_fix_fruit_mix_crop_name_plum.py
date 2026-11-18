"""Data fix: the mixed-fruit zone's third crop is plum (عوينة), not guava (كوبة).

Confirmed by the owner. Only rows still holding the old seed name are touched,
so a name the owner edited by hand is never overwritten.

Revision ID: 1eba5b0fdbf6
Revises: 0356f537da66
Create Date: 2026-11-18 21:41:34.007337
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1eba5b0fdbf6"
down_revision: str | None = "0356f537da66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("Peach + Apricot + Guava", "خوخ + مشمش + كوبة")
NEW = ("Peach + Apricot + Plum", "خوخ + مشمش + عوينة")
SQL = sa.text(
    "UPDATE zones SET name = :name, name_ar = :name_ar "
    "WHERE id = 'zone_fruit_mix' AND name = :old_name AND name_ar = :old_name_ar"
)


def upgrade() -> None:
    op.get_bind().execute(
        SQL, {"name": NEW[0], "name_ar": NEW[1], "old_name": OLD[0], "old_name_ar": OLD[1]}
    )


def downgrade() -> None:
    op.get_bind().execute(
        SQL, {"name": OLD[0], "name_ar": OLD[1], "old_name": NEW[0], "old_name_ar": NEW[1]}
    )
