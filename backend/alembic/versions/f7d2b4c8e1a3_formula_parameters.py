"""formula measure and parameters

Revision ID: f7d2b4c8e1a3
Revises: e6c4a1b8d2f0
Create Date: 2026-10-30 09:40:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f7d2b4c8e1a3"
down_revision: Union[str, None] = "e6c4a1b8d2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_formulas") as batch_op:
        batch_op.add_column(sa.Column("measure_unit_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_task_formulas_measure_unit", "units_of_measure", ["measure_unit_id"], ["id"])
    op.create_table(
        "task_formula_parameters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("formula_id", sa.Integer(), sa.ForeignKey("task_formulas.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units_of_measure.id"), nullable=False),
        sa.Column("counts", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_task_formula_parameters_formula_id", "task_formula_parameters", ["formula_id"])
    op.create_table(
        "task_parameter_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("parameter_id", sa.Integer(), sa.ForeignKey("task_formula_parameters.id"), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=True),
        sa.UniqueConstraint("task_id", "parameter_id", name="uq_task_parameter"),
    )
    op.create_index("ix_task_parameter_values_task_id", "task_parameter_values", ["task_id"])
    op.create_index("ix_task_parameter_values_parameter_id", "task_parameter_values", ["parameter_id"])


def downgrade() -> None:
    op.drop_index("ix_task_parameter_values_parameter_id", table_name="task_parameter_values")
    op.drop_index("ix_task_parameter_values_task_id", table_name="task_parameter_values")
    op.drop_table("task_parameter_values")
    op.drop_index("ix_task_formula_parameters_formula_id", table_name="task_formula_parameters")
    op.drop_table("task_formula_parameters")
    with op.batch_alter_table("task_formulas") as batch_op:
        batch_op.drop_constraint("fk_task_formulas_measure_unit", type_="foreignkey")
        batch_op.drop_column("measure_unit_id")
