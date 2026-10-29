from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import InventoryAdjustment, InventoryMovement, Location, Material, UnitOfMeasure, User
from app.models.enums import MovementType, RecordStatus
from app.services.common import (
    as_qty,
    assert_non_negative,
    assert_precision,
    audit,
    ensure_active,
    get_or_404,
    now_utc,
    require_reason,
    require_user,
)
from app.services.stock import apply_movement, get_on_hand, rebuild_balance, void_movement


def register_adjustment(
    db: Session,
    user: User,
    material_id: int,
    location_id: int,
    counted_qty: Decimal,
    reason: str,
    occurred_at: datetime | None,
) -> InventoryAdjustment:
    require_user(user)
    reason = require_reason(reason)
    material = get_or_404(db, Material, material_id, "el material")
    ensure_active(material, "El material")
    location = get_or_404(db, Location, location_id, "la ubicación")
    ensure_active(location, "La ubicación")
    unit = db.get(UnitOfMeasure, material.unit_id)
    counted = as_qty(counted_qty)
    assert_non_negative(counted, "La cantidad contada")
    assert_precision(counted, unit.decimal_places if unit else 4, "La cantidad contada")
    previous = get_on_hand(db, material.id, location.id)
    difference = as_qty(counted - previous)
    when = occurred_at or now_utc()
    adjustment = InventoryAdjustment(
        material_id=material.id,
        location_id=location.id,
        previous_qty=previous,
        counted_qty=counted,
        difference=difference,
        reason=reason,
        recorded_by_user_id=user.id,
        occurred_at=when,
        status=RecordStatus.CONFIRMADO.value,
        created_at=now_utc(),
    )
    db.add(adjustment)
    db.flush()
    if difference != 0:
        movement = apply_movement(
            db,
            movement_type=MovementType.ADJUSTMENT,
            material=material,
            location_id=location.id,
            signed_qty=difference,
            user=user,
            document_type="inventory_adjustment",
            document_id=adjustment.id,
            notes=reason,
            occurred_at=when,
        )
        adjustment.movement_id = movement.id
    db.flush()
    audit(
        db,
        user,
        "REGISTRAR_AJUSTE",
        "inventory_adjustment",
        adjustment.id,
        {"previous_qty": str(previous)},
        {"counted_qty": str(counted), "difference": str(difference)},
        reason,
    )
    return adjustment


def edit_adjustment(db: Session, adjustment: InventoryAdjustment, user: User, counted_qty: Decimal, reason: str) -> InventoryAdjustment:
    require_user(user)
    reason = require_reason(reason)
    if adjustment.status != RecordStatus.CONFIRMADO.value:
        raise AppError(422, "El ajuste no está confirmado.")
    material = db.get(Material, adjustment.material_id)
    unit = db.get(UnitOfMeasure, material.unit_id)
    counted = as_qty(counted_qty)
    assert_non_negative(counted, "La cantidad contada")
    assert_precision(counted, unit.decimal_places if unit else 4, "La cantidad contada")
    difference = as_qty(counted - Decimal(str(adjustment.previous_qty)))
    before = {"counted_qty": str(adjustment.counted_qty), "difference": str(adjustment.difference)}
    adjustment.counted_qty = counted
    adjustment.difference = difference
    if adjustment.movement_id:
        movement = db.get(InventoryMovement, adjustment.movement_id)
        if difference == 0:
            void_movement(db, movement, user, reason)
            adjustment.movement_id = None
        else:
            movement.signed_qty = difference
            rebuild_balance(db, adjustment.material_id, adjustment.location_id)
    elif difference != 0:
        movement = apply_movement(
            db,
            movement_type=MovementType.ADJUSTMENT,
            material=material,
            location_id=adjustment.location_id,
            signed_qty=difference,
            user=user,
            document_type="inventory_adjustment",
            document_id=adjustment.id,
            notes=reason,
            occurred_at=adjustment.occurred_at,
        )
        adjustment.movement_id = movement.id
    db.flush()
    audit(db, user, "CORREGIR_AJUSTE", "inventory_adjustment", adjustment.id, before, {"counted_qty": str(counted), "difference": str(difference)}, reason)
    return adjustment


def void_adjustment(db: Session, adjustment: InventoryAdjustment, user: User, reason: str) -> InventoryAdjustment:
    require_user(user)
    reason = require_reason(reason)
    if adjustment.status == RecordStatus.ANULADO.value:
        raise AppError(422, "El ajuste ya está anulado.")
    before = {"counted_qty": str(adjustment.counted_qty), "difference": str(adjustment.difference)}
    if adjustment.movement_id:
        movement = db.get(InventoryMovement, adjustment.movement_id)
        if movement and movement.status == RecordStatus.CONFIRMADO.value:
            void_movement(db, movement, user, reason)
    adjustment.status = RecordStatus.ANULADO.value
    adjustment.voided_by_user_id = user.id
    adjustment.voided_at = now_utc()
    adjustment.void_reason = reason
    db.flush()
    audit(db, user, "ANULAR_AJUSTE", "inventory_adjustment", adjustment.id, before, {"status": adjustment.status}, reason)
    return adjustment
