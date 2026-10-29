"""task dimensions and waste margin

Revision ID: d5b8e3c1a7f2
Revises: c4a9d2e7b1f3
Create Date: 2026-10-29 11:20:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5b8e3c1a7f2"
down_revision: Union[str, None] = "c4a9d2e7b1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rubrics") as batch_op:
        batch_op.add_column(sa.Column("waste_percent", sa.Numeric(18, 4), nullable=False, server_default="0"))
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("length_m", sa.Numeric(18, 4), nullable=True))
        batch_op.add_column(sa.Column("width_m", sa.Numeric(18, 4), nullable=True))
        batch_op.add_column(sa.Column("thickness_m", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("thickness_m")
        batch_op.drop_column("width_m")
        batch_op.drop_column("length_m")
    with op.batch_alter_table("rubrics") as batch_op:
        batch_op.drop_column("waste_percent")
