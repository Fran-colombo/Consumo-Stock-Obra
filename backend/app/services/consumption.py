from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import InventoryMovement, Location, Material, MaterialConsumption, Task, UnitOfMeasure, User, Work
from app.models.enums import MovementType, RecordStatus
from app.services.common import (
    as_qty,
    assert_positive,
    assert_precision,
    audit,
    ensure_active,
    get_or_404,
    now_utc,
    require_reason,
    require_user,
)
from app.services.stock import apply_movement, rebuild_balance, void_movement


def _corrections_qty(db: Session, consumption_id: int) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(MaterialConsumption.quantity), 0)).where(
            MaterialConsumption.corrects_consumption_id == consumption_id,
            MaterialConsumption.status == RecordStatus.CONFIRMADO.value,
        )
    )
    return as_qty(total or 0)


def register_consumption(
    db: Session,
    user: User,
    work_id: int,
    task_id: int,
    location_id: int,
    material_id: int,
    quantity: Decimal,
    consumed_at: datetime | None,
    notes: str | None,
) -> MaterialConsumption:
    require_user(user)
    work = get_or_404(db, Work, work_id, "la obra")
    task = get_or_404(db, Task, task_id, "la tarea")
    if task.work_id != work.id:
        raise AppError(422, "La tarea no pertenece a la obra seleccionada.")
    location = get_or_404(db, Location, location_id, "la ubicación")
    ensure_active(location, "La ubicación")
    material = get_or_404(db, Material, material_id, "el material")
    ensure_active(material, "El material")
    unit = db.get(UnitOfMeasure, material.unit_id)
    qty = as_qty(quantity)
    assert_positive(qty, "La cantidad consumida")
    assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad consumida")
    when = consumed_at or now_utc()
    consumption = MaterialConsumption(
        work_id=work.id,
        task_id=task.id,
        location_id=location.id,
        material_id=material.id,
        quantity=qty,
        unit_id=material.unit_id,
        consumed_at=when,
        recorded_by_user_id=user.id,
        notes=(notes or "").strip() or None,
        status=RecordStatus.CONFIRMADO.value,
        created_at=now_utc(),
    )
    db.add(consumption)
    db.flush()
    movement = apply_movement(
        db,
        movement_type=MovementType.CONSUMPTION,
        material=material,
        location_id=location.id,
        signed_qty=-qty,
        user=user,
        document_type="material_consumption",
        document_id=consumption.id,
        notes=notes,
        occurred_at=when,
    )
    consumption.movement_id = movement.id
    db.flush()
    audit(
        db,
        user,
        "REGISTRAR_CONSUMO",
        "material_consumption",
        consumption.id,
        None,
        {"work_id": work.id, "task_id": task.id, "material_id": material.id, "quantity": str(qty), "location_id": location.id},
    )
    return consumption


def correct_consumption(
    db: Session,
    user: User,
    original: MaterialConsumption,
    quantity: Decimal,
    reason: str,
    consumed_at: datetime | None,
) -> MaterialConsumption:
    require_user(user)
    reason = require_reason(reason)
    if original.corrects_consumption_id is not None:
        raise AppError(422, "La corrección se registra sobre el consumo original.")
    if original.status != RecordStatus.CONFIRMADO.value:
        raise AppError(422, "El consumo original no está confirmado.")
    unit = db.get(UnitOfMeasure, original.unit_id)
    qty = as_qty(quantity)
    assert_positive(qty, "La cantidad de la corrección")
    assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad de la corrección")
    remaining = as_qty(Decimal(str(original.quantity)) - _corrections_qty(db, original.id))
    if qty > remaining:
        raise AppError(422, "La corrección supera la cantidad pendiente de ese consumo.")
    material = db.get(Material, original.material_id)
    when = consumed_at or now_utc()
    correction = MaterialConsumption(
        work_id=original.work_id,
        task_id=original.task_id,
        location_id=original.location_id,
        material_id=original.material_id,
        quantity=qty,
        unit_id=original.unit_id,
        consumed_at=when,
        recorded_by_user_id=user.id,
        notes=reason,
        status=RecordStatus.CONFIRMADO.value,
        corrects_consumption_id=original.id,
        created_at=now_utc(),
    )
    db.add(correction)
    db.flush()
    movement = apply_movement(
        db,
        movement_type=MovementType.CONSUMPTION_REVERSAL,
        material=material,
        location_id=original.location_id,
        signed_qty=qty,
        user=user,
        document_type="material_consumption",
        document_id=correction.id,
        notes=reason,
        occurred_at=when,
        corrects_movement_id=original.movement_id,
    )
    correction.movement_id = movement.id
    db.flush()
    audit(
        db,
        user,
        "CORREGIR_CONSUMO",
        "material_consumption",
        correction.id,
        {"original_id": original.id},
        {"quantity": str(qty)},
        reason,
    )
    return correction


def edit_consumption(db: Session, consumption: MaterialConsumption, user: User, quantity: Decimal, reason: str) -> MaterialConsumption:
    require_user(user)
    reason = require_reason(reason)
    if consumption.status != RecordStatus.CONFIRMADO.value or consumption.corrects_consumption_id is not None:
        raise AppError(422, "Solo se puede corregir la cantidad de un consumo confirmado.")
    unit = db.get(UnitOfMeasure, consumption.unit_id)
    qty = as_qty(quantity)
    assert_positive(qty, "La cantidad consumida")
    assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad consumida")
    if qty < _corrections_qty(db, consumption.id):
        raise AppError(422, "La cantidad queda por debajo de las correcciones ya registradas.")
    movement = db.get(InventoryMovement, consumption.movement_id)
    before = str(consumption.quantity)
    consumption.quantity = qty
    movement.signed_qty = -qty
    rebuild_balance(db, consumption.material_id, consumption.location_id)
    db.flush()
    audit(db, user, "CORREGIR_CONSUMO", "material_consumption", consumption.id, {"quantity": before}, {"quantity": str(qty)}, reason)
    return consumption


def void_consumption(db: Session, consumption: MaterialConsumption, user: User, reason: str) -> MaterialConsumption:
    require_user(user)
    reason = require_reason(reason)
    if consumption.status == RecordStatus.ANULADO.value:
        raise AppError(422, "El consumo ya está anulado.")
    if _corrections_qty(db, consumption.id) > 0:
        raise AppError(422, "Anulá primero las correcciones de este consumo.")
    before = {"quantity": str(consumption.quantity), "status": consumption.status}
    if consumption.movement_id:
        movement = db.get(InventoryMovement, consumption.movement_id)
        if movement and movement.status == RecordStatus.CONFIRMADO.value:
            void_movement(db, movement, user, reason)
    consumption.status = RecordStatus.ANULADO.value
    consumption.voided_by_user_id = user.id
    consumption.voided_at = now_utc()
    consumption.void_reason = reason
    db.flush()
    audit(db, user, "ANULAR_CONSUMO", "material_consumption", consumption.id, before, {"status": consumption.status}, reason)
    return consumption
