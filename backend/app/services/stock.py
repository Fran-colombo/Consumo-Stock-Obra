from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import InventoryMovement, Material, StockBalance, UnitOfMeasure
from app.models.enums import MovementType, RecordStatus
from app.services.common import as_qty, assert_precision, audit, now_utc, require_user, setting_bool


def get_on_hand(db: Session, material_id: int, location_id: int) -> Decimal:
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.material_id == material_id,
            StockBalance.location_id == location_id,
        )
    )
    if balance is None:
        return Decimal("0.0000")
    return as_qty(balance.on_hand)


def _ensure_balance(db: Session, material_id: int, location_id: int) -> StockBalance:
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.material_id == material_id,
            StockBalance.location_id == location_id,
        )
    )
    if balance is None:
        balance = StockBalance(material_id=material_id, location_id=location_id, on_hand=Decimal("0.0000"))
        db.add(balance)
        db.flush()
    return balance


def ledger_total(db: Session, material_id: int, location_id: int) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(InventoryMovement.signed_qty), 0)).where(
            InventoryMovement.material_id == material_id,
            InventoryMovement.location_id == location_id,
            InventoryMovement.status == RecordStatus.CONFIRMADO.value,
        )
    )
    return as_qty(total or 0)


def rebuild_balance(db: Session, material_id: int, location_id: int) -> Decimal:
    total = ledger_total(db, material_id, location_id)
    if total < 0 and not setting_bool(db, "allow_negative_stock"):
        raise AppError(409, "La corrección dejaría el stock por debajo de cero y el stock negativo está desactivado.")
    balance = _ensure_balance(db, material_id, location_id)
    balance.on_hand = total
    db.flush()
    return total


def apply_movement(
    db: Session,
    *,
    movement_type: MovementType,
    material: Material,
    location_id: int,
    signed_qty: Decimal,
    user,
    document_type: str,
    document_id: int,
    reference_code: str | None = None,
    notes: str | None = None,
    occurred_at=None,
    corrects_movement_id: int | None = None,
) -> InventoryMovement:
    actor = require_user(user)
    signed_qty = as_qty(signed_qty)
    unit = db.get(UnitOfMeasure, material.unit_id)
    assert_precision(abs(signed_qty), unit.decimal_places if unit else 4, "La cantidad")
    if signed_qty == 0:
        raise AppError(422, "La cantidad del movimiento no puede ser cero.")
    movement = InventoryMovement(
        movement_type=movement_type.value,
        material_id=material.id,
        location_id=location_id,
        signed_qty=signed_qty,
        unit_id=material.unit_id,
        occurred_at=occurred_at or now_utc(),
        recorded_by_user_id=actor.id,
        document_type=document_type,
        document_id=document_id,
        reference_code=reference_code,
        notes=notes,
        status=RecordStatus.CONFIRMADO.value,
        corrects_movement_id=corrects_movement_id,
        created_at=now_utc(),
    )
    db.add(movement)
    db.flush()
    balance = _ensure_balance(db, material.id, location_id)
    allow_negative = setting_bool(db, "allow_negative_stock")
    if signed_qty < 0 and not allow_negative:
        result = db.execute(
            update(StockBalance)
            .where(StockBalance.id == balance.id, StockBalance.on_hand >= -signed_qty)
            .values(on_hand=StockBalance.on_hand + signed_qty)
        )
        if result.rowcount != 1:
            available = get_on_hand(db, material.id, location_id)
            raise AppError(
                409,
                f"No hay stock suficiente de {material.name}. Disponible: {available}.",
            )
    else:
        db.execute(
            update(StockBalance)
            .where(StockBalance.id == balance.id)
            .values(on_hand=StockBalance.on_hand + signed_qty)
        )
    db.expire(balance)
    return movement


def void_movement(db: Session, movement: InventoryMovement, user, reason: str) -> None:
    require_user(user)
    if movement.status == RecordStatus.ANULADO.value:
        raise AppError(422, "El movimiento ya está anulado.")
    movement.status = RecordStatus.ANULADO.value
    movement.voided_by_user_id = user.id
    movement.voided_at = now_utc()
    movement.void_reason = reason
    rebuild_balance(db, movement.material_id, movement.location_id)


def set_movement_qty(db: Session, movement: InventoryMovement, signed_qty: Decimal, user, reason: str) -> None:
    require_user(user)
    if movement.status != RecordStatus.CONFIRMADO.value:
        raise AppError(422, "Solo se puede corregir un movimiento confirmado.")
    signed_qty = as_qty(signed_qty)
    material = db.get(Material, movement.material_id)
    unit = db.get(UnitOfMeasure, material.unit_id) if material else None
    assert_precision(abs(signed_qty), unit.decimal_places if unit else 4, "La cantidad")
    if signed_qty == 0:
        raise AppError(422, "La cantidad no puede quedar en cero. Anulá el registro si corresponde.")
    before = str(movement.signed_qty)
    movement.signed_qty = signed_qty
    rebuild_balance(db, movement.material_id, movement.location_id)
    audit(
        db,
        user,
        "CORREGIR_MOVIMIENTO",
        "inventory_movement",
        movement.id,
        {"signed_qty": before},
        {"signed_qty": str(signed_qty)},
        reason,
    )


def consistency_report(db: Session) -> list[dict]:
    mismatches = []
    balances = db.scalars(select(StockBalance)).all()
    seen: set[tuple[int, int]] = set()
    for balance in balances:
        total = ledger_total(db, balance.material_id, balance.location_id)
        seen.add((balance.material_id, balance.location_id))
        if as_qty(balance.on_hand) != total:
            mismatches.append(
                {
                    "material_id": balance.material_id,
                    "location_id": balance.location_id,
                    "balance": str(as_qty(balance.on_hand)),
                    "ledger": str(total),
                }
            )
    pairs = db.execute(
        select(InventoryMovement.material_id, InventoryMovement.location_id)
        .where(InventoryMovement.status == RecordStatus.CONFIRMADO.value)
        .distinct()
    ).all()
    for material_id, location_id in pairs:
        if (material_id, location_id) in seen:
            continue
        total = ledger_total(db, material_id, location_id)
        if total != 0:
            mismatches.append(
                {
                    "material_id": material_id,
                    "location_id": location_id,
                    "balance": "0.0000",
                    "ledger": str(total),
                }
            )
    return mismatches
