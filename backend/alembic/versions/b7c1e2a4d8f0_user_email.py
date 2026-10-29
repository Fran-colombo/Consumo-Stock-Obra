"""user email

Revision ID: b7c1e2a4d8f0
Revises: ee3f5bec5a9c
Create Date: 2026-10-29 10:05:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7c1e2a4d8f0"
down_revision: Union[str, None] = "ee3f5bec5a9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=160), nullable=True))
        batch_op.create_index("ix_users_email", ["email"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_email")
        batch_op.drop_column("email")
