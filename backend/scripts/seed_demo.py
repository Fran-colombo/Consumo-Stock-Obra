"""Datos de demostración, separados de la operación real.

El coeficiente de 6 unidades por m³ es ilustrativo. No es una recomendación técnica de Conkreto.
"""

import argparse

from sqlalchemy import func, select

from app.core import database
from app.models.entities import Location, UnitOfMeasure, User, Work
from app.models.enums import UserRole
from app.services.consumption import register_consumption
from app.services.planning import create_material, create_rubric, create_rule, create_task, create_work, record_execution
from app.services.purchasing import confirm_purchase_order, create_purchase_order, create_supplier, register_receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga el ejemplo ilustrativo de Conkreto.")
    parser.add_argument("--force", action="store_true", help="Permite cargar aunque ya existan obras.")
    args = parser.parse_args()
    database.get_engine()
    db = database.SessionLocal()
    try:
        works = db.scalar(select(func.count()).select_from(Work)) or 0
        if works and not args.force:
            raise SystemExit("Ya hay obras en la base. No se cargó la demostración. Usá --force si querés agregarla igual.")
        user = db.scalar(select(User).where(User.role == UserRole.SYSADMIN.value))
        if user is None:
            raise SystemExit("No hay un administrador. Iniciá la API una vez con las variables CONKRETO_SYSADMIN_* y volvé a correr este script.")
        unit = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "u"))
        cubic = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "m3"))
        if unit is None or cubic is None:
            raise SystemExit("Faltan las unidades de medida. Aplicá las migraciones antes de la demostración.")
        note = "DATO DE DEMOSTRACIÓN. El coeficiente 6 es ilustrativo y no es una recomendación técnica."
        work = create_work(db, user, "Obra de prueba A", "OBRA-DEMO-A", "Ejemplo", "ACTIVA", None, note)
        rubric = create_rubric(db, user, "Contrapiso", "RUB-DEMO-CONTRAPISO", note)
        material = create_material(db, user, "Cemento", "MAT-DEMO-CEMENTO", unit.id, "Demostración", note, note, None)
        task = create_task(db, user, work.id, rubric.id, "Ejecución de contrapiso", note, cubic.id, None, None, None, "EN_CURSO", note)
        create_rule(db, user, task, material.id, 6, unit.id, note)
        record_execution(db, user, task, 10, None, None, note)
        supplier = create_supplier(db, user, "Proveedor de demostración", None)
        location = db.scalar(select(Location).where(Location.work_id == work.id))
        order = create_purchase_order(
            db,
            user,
            supplier.id,
            location.id,
            work.id,
            None,
            note,
            [{"material_id": material.id, "quantity": 100, "unit_price": None, "currency": None}],
        )
        confirm_purchase_order(db, order, user)
        register_receipt(db, user, order, location.id, [{"purchase_order_item_id": order.items[0].id, "quantity": 60}], None, note)
        register_receipt(db, user, order, location.id, [{"purchase_order_item_id": order.items[0].id, "quantity": 40}], None, note)
        register_consumption(db, user, work.id, task.id, location.id, material.id, 55, None, note)
        db.commit()
        print(note)
        print("Quedó cargada la obra OBRA-DEMO-A: teórico 60, real 55, diferencia -5, saldo 45.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
