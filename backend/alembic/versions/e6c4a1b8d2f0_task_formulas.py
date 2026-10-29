"""task formulas

Revision ID: e6c4a1b8d2f0
Revises: d5b8e3c1a7f2
Create Date: 2026-10-29 11:35:00

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e6c4a1b8d2f0"
down_revision: Union[str, None] = "d5b8e3c1a7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_formulas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("waste_percent", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_formulas_name", "task_formulas", ["name"])
    op.create_table(
        "task_formula_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("formula_id", sa.Integer(), sa.ForeignKey("task_formulas.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("coefficient", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("formula_id", "material_id", name="uq_formula_material"),
    )
    op.create_index("ix_task_formula_lines_formula_id", "task_formula_lines", ["formula_id"])
    op.create_index("ix_task_formula_lines_material_id", "task_formula_lines", ["material_id"])
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("formula_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("waste_percent", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch_op.create_foreign_key("fk_tasks_formula", "task_formulas", ["formula_id"], ["id"])

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    rubrics = bind.execute(sa.text("SELECT id, name, waste_percent FROM rubrics")).fetchall()
    for rubric in rubrics:
        lines = bind.execute(
            sa.text("SELECT material_id, coefficient FROM rubric_recipe_lines WHERE rubric_id = :rubric_id"),
            {"rubric_id": rubric.id},
        ).fetchall()
        if not lines:
            continue
        inserted = bind.execute(
            sa.text(
                "INSERT INTO task_formulas (name, waste_percent, is_active, created_at) VALUES (:name, :waste, 1, :created_at)"
            ),
            {"name": rubric.name, "waste": rubric.waste_percent, "created_at": now},
        )
        formula_id = inserted.lastrowid
        for line in lines:
            bind.execute(
                sa.text(
                    "INSERT INTO task_formula_lines (formula_id, material_id, coefficient) VALUES (:formula_id, :material_id, :coefficient)"
                ),
                {"formula_id": formula_id, "material_id": line.material_id, "coefficient": line.coefficient},
            )
        bind.execute(
            sa.text(
                "UPDATE tasks SET formula_id = :formula_id, waste_percent = :waste WHERE rubric_id = :rubric_id AND length_m IS NOT NULL"
            ),
            {"formula_id": formula_id, "waste": rubric.waste_percent, "rubric_id": rubric.id},
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_formula", type_="foreignkey")
        batch_op.drop_column("waste_percent")
        batch_op.drop_column("formula_id")
    op.drop_index("ix_task_formula_lines_material_id", table_name="task_formula_lines")
    op.drop_index("ix_task_formula_lines_formula_id", table_name="task_formula_lines")
    op.drop_table("task_formula_lines")
    op.drop_index("ix_task_formulas_name", table_name="task_formulas")
    op.drop_table("task_formulas")
