"""recipe and pending reason

Revision ID: c4a9d2e7b1f3
Revises: b7c1e2a4d8f0
Create Date: 2026-10-29 11:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4a9d2e7b1f3"
down_revision: Union[str, None] = "b7c1e2a4d8f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rubrics") as batch_op:
        batch_op.add_column(sa.Column("coverage_unit_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_rubrics_coverage_unit", "units_of_measure", ["coverage_unit_id"], ["id"])
    op.create_table(
        "rubric_recipe_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rubric_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("coefficient", sa.Numeric(18, 4), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rubric_id", "material_id", name="uq_rubric_recipe_material"),
    )
    with op.batch_alter_table("rubric_recipe_lines") as batch_op:
        batch_op.create_index("ix_rubric_recipe_lines_material_id", ["material_id"], unique=False)
        batch_op.create_index("ix_rubric_recipe_lines_rubric_id", ["rubric_id"], unique=False)
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("pending_reason", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("pending_reason")
    op.drop_table("rubric_recipe_lines")
    with op.batch_alter_table("rubrics") as batch_op:
        batch_op.drop_constraint("fk_rubrics_coverage_unit", type_="foreignkey")
        batch_op.drop_column("coverage_unit_id")
