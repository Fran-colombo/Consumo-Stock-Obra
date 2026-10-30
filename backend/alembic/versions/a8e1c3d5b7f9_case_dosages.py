"""case dosages

Revision ID: a8e1c3d5b7f9
Revises: f7d2b4c8e1a3
Create Date: 2026-10-30 11:05:00

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a8e1c3d5b7f9"
down_revision: Union[str, None] = "f7d2b4c8e1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNITS = [
    ("kg", "Kilogramo", 3),
    ("m3", "Metro cúbico", 3),
    ("m2", "Metro cuadrado", 3),
    ("m", "Metro", 3),
    ("u", "Unidad", 0),
    ("cm", "Centímetro", 2),
]

MATERIALS = [
    ("DOS-CEM-ALB", "Cemento de albañilería", "kg"),
    ("DOS-CEM-PORT", "Cemento Portland", "kg"),
    ("DOS-CAL", "Cal hidratada", "kg"),
    ("DOS-ARENA-F", "Arena fina", "m3"),
    ("DOS-ARENA-G", "Arena gruesa", "m3"),
    ("DOS-CASCOTE", "Cascote molido", "m3"),
    ("DOS-PIEDRA", "Piedra partida", "m3"),
    ("DOS-LAD-H18", "Ladrillo hueco 18x18x33", "u"),
    ("DOS-LAD-COM", "Ladrillo común macizo", "u"),
]

CONTRAPISO_NOTE = (
    "PropData publica 16 kg de cemento, 0,03 m³ de arena gruesa y 0,04 m³ de cascote por m² a 8 cm. "
    "Acá está por m³: 200 kg, 0,375 m³ y 0,5 m³, para que el espesor cambie la cuenta."
)


def _unit(bind, code: str) -> int:
    return bind.execute(sa.text("SELECT id FROM units_of_measure WHERE code = :code"), {"code": code}).scalar_one()


def _material(bind, code: str) -> int:
    return bind.execute(sa.text("SELECT id FROM materials WHERE code = :code"), {"code": code}).scalar_one()


def upgrade() -> None:
    with op.batch_alter_table("task_formulas") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
    with op.batch_alter_table("task_formula_parameters") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=20), nullable=False, server_default="multiplica"))
        batch_op.add_column(sa.Column("factor", sa.Numeric(18, 4), nullable=False, server_default="1"))
    op.execute("UPDATE task_formula_parameters SET role = 'anota' WHERE counts = 0")

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for code, name, places in UNITS:
        exists = bind.execute(sa.text("SELECT id FROM units_of_measure WHERE code = :code"), {"code": code}).first()
        if exists is None:
            bind.execute(
                sa.text("INSERT INTO units_of_measure (code, name, decimal_places) VALUES (:code, :name, :places)"),
                {"code": code, "name": name, "places": places},
            )
    for code, name, unit_code in MATERIALS:
        exists = bind.execute(sa.text("SELECT id FROM materials WHERE code = :code"), {"code": code}).first()
        if exists is None:
            bind.execute(
                sa.text(
                    "INSERT INTO materials (code, name, unit_id, is_active, created_at) VALUES (:code, :name, :unit_id, 1, :created_at)"
                ),
                {"code": code, "name": name, "unit_id": _unit(bind, unit_code), "created_at": now},
            )

    def add_formula(name: str, unit_code: str, waste: str, notes: str | None, parameters: list, lines: list) -> None:
        exists = bind.execute(sa.text("SELECT id FROM task_formulas WHERE name = :name"), {"name": name}).first()
        if exists is not None:
            return
        inserted = bind.execute(
            sa.text(
                "INSERT INTO task_formulas (name, waste_percent, measure_unit_id, notes, is_active, created_at) "
                "VALUES (:name, :waste, :unit_id, :notes, 1, :created_at)"
            ),
            {"name": name, "waste": waste, "unit_id": _unit(bind, unit_code), "notes": notes, "created_at": now},
        )
        formula_id = inserted.lastrowid
        for position, param in enumerate(parameters, start=1):
            bind.execute(
                sa.text(
                    "INSERT INTO task_formula_parameters (formula_id, name, unit_id, counts, role, factor, position) "
                    "VALUES (:formula_id, :name, :unit_id, :counts, :role, :factor, :position)"
                ),
                {
                    "formula_id": formula_id,
                    "name": param[0],
                    "unit_id": _unit(bind, param[1]),
                    "counts": 1 if param[2] == "multiplica" else 0,
                    "role": param[2],
                    "factor": param[3],
                    "position": position,
                },
            )
        for material_code, coefficient in lines:
            bind.execute(
                sa.text(
                    "INSERT INTO task_formula_lines (formula_id, material_id, coefficient) VALUES (:formula_id, :material_id, :coefficient)"
                ),
                {"formula_id": formula_id, "material_id": _material(bind, material_code), "coefficient": coefficient},
            )

    wall = [
        ("Largo", "m", "multiplica", "1"),
        ("Alto", "m", "multiplica", "1"),
        ("Aberturas", "m2", "resta", "1"),
    ]
    volume = [
        ("Largo", "m", "multiplica", "1"),
        ("Ancho", "m", "multiplica", "1"),
        ("Espesor", "cm", "multiplica", "0.01"),
    ]
    add_formula(
        "Muro de ladrillo hueco 18, soga",
        "m2",
        "5",
        None,
        wall,
        [("DOS-LAD-H18", "16"), ("DOS-CEM-ALB", "2"), ("DOS-ARENA-F", "0.015")],
    )
    add_formula(
        "Muro de ladrillo hueco 18, inglés",
        "m2",
        "5",
        None,
        wall,
        [("DOS-LAD-H18", "30"), ("DOS-CEM-ALB", "3.5"), ("DOS-ARENA-F", "0.025")],
    )
    add_formula(
        "Muro de ladrillo común de 12 cm",
        "m2",
        "5",
        None,
        wall,
        [("DOS-LAD-COM", "28"), ("DOS-CEM-ALB", "2.8"), ("DOS-ARENA-F", "0.020")],
    )
    add_formula(
        "Revoque grueso interior",
        "m2",
        "10",
        "Publicado para un espesor de 2 cm.",
        wall,
        [("DOS-CEM-PORT", "2.5"), ("DOS-CAL", "2.5"), ("DOS-ARENA-F", "0.014")],
    )
    add_formula(
        "Revoque fino interior",
        "m2",
        "10",
        "Publicado para un espesor de 0,5 cm.",
        wall,
        [("DOS-CAL", "3"), ("DOS-ARENA-F", "0.004")],
    )
    add_formula(
        "Hormigón H21",
        "m3",
        "10",
        None,
        volume,
        [("DOS-CEM-PORT", "350"), ("DOS-ARENA-G", "0.65"), ("DOS-PIEDRA", "0.85")],
    )
    add_formula(
        "Contrapiso de cascote",
        "m3",
        "10",
        CONTRAPISO_NOTE,
        volume,
        [("DOS-CEM-PORT", "200"), ("DOS-ARENA-G", "0.375"), ("DOS-CASCOTE", "0.5")],
    )


def downgrade() -> None:
    with op.batch_alter_table("task_formula_parameters") as batch_op:
        batch_op.drop_column("factor")
        batch_op.drop_column("role")
    with op.batch_alter_table("task_formulas") as batch_op:
        batch_op.drop_column("notes")
