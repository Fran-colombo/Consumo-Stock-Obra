from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import (
    InventoryMovement,
    Location,
    Material,
    StockTransfer,
    StockTransferItem,
    TransferDiscrepancy,
    UnitOfMeasure,
    User,
)
from app.models.enums import DiscrepancyStatus, MovementType, RecordStatus, TransferStatus
from app.services.common import (
    as_qty,
    assert_positive,
    assert_precision,
    audit,
    ensure_active,
    get_or_404,
    next_number,
    now_utc,
    require_reason,
    require_user,
)
from app.services.stock import apply_movement, void_movement


def _optional_user(db: Session, user_id: int | None) -> User | None:
    if user_id is None:
        return None
    return get_or_404(db, User, user_id, "la persona")


def discrepancy_qty(db: Session, item_id: int) -> Decimal:
    rows = db.scalars(select(TransferDiscrepancy).where(TransferDiscrepancy.transfer_item_id == item_id)).all()
    return as_qty(sum((Decimal(str(row.quantity)) for row in rows), Decimal("0")))


def in_transit_qty(db: Session, item: StockTransferItem) -> Decimal:
    status = item.transfer.status
    if status in (TransferStatus.REGISTRADA.value, TransferStatus.CANCELADA.value, TransferStatus.RECIBIDA.value):
        return Decimal("0.0000")
    pending = as_qty(
        Decimal(str(item.qty_sent))
        - Decimal(str(item.qty_received))
        - Decimal(str(item.qty_returned))
        - discrepancy_qty(db, item.id)
    )
    return pending if pending > 0 else Decimal("0.0000")


def _refresh_transfer_status(db: Session, transfer: StockTransfer) -> None:
    if transfer.status == TransferStatus.CANCELADA.value:
        return
    if transfer.status == TransferStatus.REGISTRADA.value:
        return
    any_transit = False
    any_discrepancy = False
    any_received = False
    for item in transfer.items:
        if Decimal(str(item.qty_received)) > 0:
            any_received = True
        if in_transit_qty(db, item) > 0:
            any_transit = True
        rows = db.scalars(select(TransferDiscrepancy).where(TransferDiscrepancy.transfer_item_id == item.id)).all()
        if rows:
            any_discrepancy = True
    if any_transit and any_received:
        transfer.status = TransferStatus.RECIBIDA_PARCIAL.value
    elif any_transit:
        transfer.status = TransferStatus.EN_TRANSITO.value
    elif any_discrepancy:
        transfer.status = TransferStatus.RECIBIDA_CON_DIFERENCIA.value
    else:
        transfer.status = TransferStatus.RECIBIDA.value
    db.flush()


def create_transfer(
    db: Session,
    user: User,
    from_location_id: int,
    to_location_id: int,
    items: list[dict],
    notes: str | None,
    authorized_by_user_id: int | None,
    authorized_operational_name: str | None,
    authorized_at: datetime | None,
) -> StockTransfer:
    require_user(user)
    if from_location_id == to_location_id:
        raise AppError(422, "El origen y el destino tienen que ser ubicaciones distintas.")
    origin = get_or_404(db, Location, from_location_id, "la ubicación de origen")
    destination = get_or_404(db, Location, to_location_id, "la ubicación de destino")
    ensure_active(origin, "La ubicación de origen")
    ensure_active(destination, "La ubicación de destino")
    if not items:
        raise AppError(422, "La transferencia tiene que incluir al menos un material.")
    authorizer = _optional_user(db, authorized_by_user_id)
    auth_name = (authorized_operational_name or "").strip() or None
    transfer = StockTransfer(
        number=next_number(db, "TR"),
        from_location_id=origin.id,
        to_location_id=destination.id,
        status=TransferStatus.REGISTRADA.value,
        notes=(notes or "").strip() or None,
        created_by_user_id=user.id,
        created_at=now_utc(),
        authorized_by_user_id=authorizer.id if authorizer else None,
        authorized_operational_name=auth_name,
        authorized_at=(authorized_at or now_utc()) if authorizer or auth_name else None,
    )
    db.add(transfer)
    db.flush()
    seen: set[int] = set()
    for raw in items:
        material = get_or_404(db, Material, raw["material_id"], "el material")
        ensure_active(material, "El material")
        if material.id in seen:
            raise AppError(422, f"El material {material.name} está repetido en la transferencia.")
        seen.add(material.id)
        unit = db.get(UnitOfMeasure, material.unit_id)
        qty = as_qty(raw["quantity"])
        assert_positive(qty, "La cantidad a trasladar")
        assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad a trasladar")
        db.add(
            StockTransferItem(
                transfer_id=transfer.id,
                material_id=material.id,
                qty_sent=qty,
                qty_received=Decimal("0.0000"),
                qty_returned=Decimal("0.0000"),
                unit_id=material.unit_id,
            )
        )
    db.flush()
    audit(db, user, "CREAR_TRANSFERENCIA", "stock_transfer", transfer.id, None, {"number": transfer.number})
    return transfer


def dispatch_transfer(
    db: Session,
    transfer: StockTransfer,
    user: User,
    executed_by_user_id: int | None,
    executed_operational_name: str | None,
    executed_at: datetime | None,
) -> StockTransfer:
    require_user(user)
    if transfer.status != TransferStatus.REGISTRADA.value:
        raise AppError(422, "Solo se puede despachar una transferencia registrada.")
    executor = _optional_user(db, executed_by_user_id)
    when = executed_at or now_utc()
    for item in transfer.items:
        movement = apply_movement(
            db,
            movement_type=MovementType.TRANSFER_OUT,
            material=item.material,
            location_id=transfer.from_location_id,
            signed_qty=-Decimal(str(item.qty_sent)),
            user=user,
            document_type="stock_transfer",
            document_id=transfer.id,
            reference_code=transfer.number,
            occurred_at=when,
        )
        item.out_movement_id = movement.id
    transfer.status = TransferStatus.EN_TRANSITO.value
    transfer.executed_by_user_id = executor.id if executor else None
    transfer.executed_operational_name = (executed_operational_name or "").strip() or None
    transfer.executed_at = when
    db.flush()
    audit(db, user, "DESPACHAR_TRANSFERENCIA", "stock_transfer", transfer.id, {"status": "REGISTRADA"}, {"status": transfer.status})
    return transfer


def receive_transfer(
    db: Session,
    transfer: StockTransfer,
    user: User,
    lines: list[dict],
    received_by_user_id: int | None,
    received_operational_name: str | None,
    close_with_difference: bool,
    received_at: datetime | None,
    notes: str | None,
) -> StockTransfer:
    require_user(user)
    if transfer.status not in (TransferStatus.EN_TRANSITO.value, TransferStatus.RECIBIDA_PARCIAL.value):
        raise AppError(422, "La transferencia no está en tránsito.")
    receiver = _optional_user(db, received_by_user_id)
    by_id = {item.id: item for item in transfer.items}
    when = received_at or now_utc()
    seen: set[int] = set()
    for raw in lines:
        item = by_id.get(raw["transfer_item_id"])
        if item is None:
            raise AppError(422, "Hay un material que no pertenece a la transferencia.")
        if item.id in seen:
            raise AppError(422, "Hay un material repetido en la recepción.")
        seen.add(item.id)
        unit = db.get(UnitOfMeasure, item.unit_id)
        qty = as_qty(raw["quantity"])
        if qty < 0:
            raise AppError(422, "La cantidad recibida no puede ser negativa.")
        assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad recibida")
        remaining = in_transit_qty(db, item)
        if qty > remaining:
            raise AppError(422, f"No se puede recibir más {item.material.name} del que sigue en tránsito.")
        if qty > 0:
            movement = apply_movement(
                db,
                movement_type=MovementType.TRANSFER_IN,
                material=item.material,
                location_id=transfer.to_location_id,
                signed_qty=qty,
                user=user,
                document_type="stock_transfer",
                document_id=transfer.id,
                reference_code=transfer.number,
                notes=notes,
                occurred_at=when,
            )
            item.qty_received = as_qty(Decimal(str(item.qty_received)) + qty)
            item.in_movement_id = movement.id
    if close_with_difference:
        for item in transfer.items:
            short = in_transit_qty(db, item)
            if short > 0:
                db.add(
                    TransferDiscrepancy(
                        transfer_item_id=item.id,
                        quantity=short,
                        status=DiscrepancyStatus.PENDIENTE.value,
                        created_at=now_utc(),
                    )
                )
        db.flush()
    transfer.received_by_user_id = receiver.id if receiver else transfer.received_by_user_id
    name = (received_operational_name or "").strip()
    if name:
        transfer.received_operational_name = name
    if lines or close_with_difference:
        transfer.received_at = when
    if notes:
        transfer.notes = ((transfer.notes or "") + "\n" + notes.strip()).strip()
    _refresh_transfer_status(db, transfer)
    audit(db, user, "RECIBIR_TRANSFERENCIA", "stock_transfer", transfer.id, None, {"status": transfer.status, "close_with_difference": close_with_difference})
    return transfer


def move_stock(
    db: Session,
    user: User,
    from_location_id: int,
    to_location_id: int,
    material_id: int,
    quantity: Decimal,
    received_quantity: Decimal | None,
    shortfall_action: str | None,
    reason: str | None,
) -> StockTransfer:
    transfer = create_transfer(
        db,
        user,
        from_location_id,
        to_location_id,
        [{"material_id": material_id, "quantity": quantity}],
        None,
        None,
        None,
        None,
    )
    dispatch_transfer(db, transfer, user, None, None, None)
    item = transfer.items[0]
    sent = as_qty(item.qty_sent)
    arrived = sent if received_quantity is None else as_qty(received_quantity)
    if arrived < 0:
        raise AppError(422, "La cantidad que llegó no puede ser negativa.")
    if arrived > sent:
        raise AppError(422, "No puede llegar más de lo que salió.")
    short = arrived < sent
    if short and not shortfall_action:
        raise AppError(422, "Si llegó menos, indicá qué pasó con el faltante.")
    if short and not (reason or "").strip():
        raise AppError(422, "Si llegó menos, escribí el motivo.")
    receive_transfer(
        db,
        transfer,
        user,
        [{"transfer_item_id": item.id, "quantity": arrived}],
        None,
        None,
        short,
        None,
        reason,
    )
    if short:
        discrepancy = db.scalar(
            select(TransferDiscrepancy).where(
                TransferDiscrepancy.transfer_item_id == item.id,
                TransferDiscrepancy.status == DiscrepancyStatus.PENDIENTE.value,
            )
        )
        if discrepancy is None:
            raise AppError(422, "No quedó registrado el faltante.")
        resolve_discrepancy(db, discrepancy, user, shortfall_action or "", reason or "")
    return transfer


def cancel_transfer(db: Session, transfer: StockTransfer, user: User, reason: str) -> StockTransfer:
    require_user(user)
    reason = require_reason(reason)
    if transfer.status == TransferStatus.CANCELADA.value:
        raise AppError(422, "La transferencia ya está cancelada.")
    if transfer.status == TransferStatus.REGISTRADA.value:
        transfer.status = TransferStatus.CANCELADA.value
        db.flush()
        audit(db, user, "CANCELAR_TRANSFERENCIA", "stock_transfer", transfer.id, {"status": "REGISTRADA"}, {"status": transfer.status}, reason)
        return transfer
    if transfer.status not in (TransferStatus.EN_TRANSITO.value, TransferStatus.RECIBIDA_PARCIAL.value):
        raise AppError(422, "Esta transferencia ya no se puede cancelar. Resolvé las diferencias o pedile al administrador que la anule.")
    open_diff = db.scalar(
        select(TransferDiscrepancy)
        .join(StockTransferItem, StockTransferItem.id == TransferDiscrepancy.transfer_item_id)
        .where(
            StockTransferItem.transfer_id == transfer.id,
            TransferDiscrepancy.status == DiscrepancyStatus.PENDIENTE.value,
        )
    )
    if open_diff is not None:
        raise AppError(422, "Hay diferencias pendientes. Resolvelas antes de cancelar.")
    before = transfer.status
    for item in transfer.items:
        pending = in_transit_qty(db, item)
        if pending > 0:
            apply_movement(
                db,
                movement_type=MovementType.TRANSFER_RETURN,
                material=item.material,
                location_id=transfer.from_location_id,
                signed_qty=pending,
                user=user,
                document_type="stock_transfer",
                document_id=transfer.id,
                reference_code=transfer.number,
                notes=reason,
            )
            item.qty_returned = as_qty(Decimal(str(item.qty_returned)) + pending)
    transfer.status = TransferStatus.CANCELADA.value
    db.flush()
    audit(db, user, "CANCELAR_TRANSFERENCIA", "stock_transfer", transfer.id, {"status": before}, {"status": transfer.status}, reason)
    return transfer


def resolve_discrepancy(
    db: Session,
    discrepancy: TransferDiscrepancy,
    user: User,
    action: str,
    reason: str,
) -> TransferDiscrepancy:
    require_user(user)
    reason = require_reason(reason)
    if discrepancy.status != DiscrepancyStatus.PENDIENTE.value:
        raise AppError(422, "La diferencia ya fue resuelta.")
    item = discrepancy.item
    transfer = item.transfer
    qty = as_qty(discrepancy.quantity)
    if action == "devolver":
        movement = apply_movement(
            db,
            movement_type=MovementType.TRANSFER_RETURN,
            material=item.material,
            location_id=transfer.from_location_id,
            signed_qty=qty,
            user=user,
            document_type="stock_transfer",
            document_id=transfer.id,
            reference_code=transfer.number,
            notes=reason,
        )
        item.qty_returned = as_qty(Decimal(str(item.qty_returned)) + qty)
        discrepancy.status = DiscrepancyStatus.DEVUELTA.value
        discrepancy.movement_id = movement.id
    elif action == "perdida":
        discrepancy.status = DiscrepancyStatus.PERDIDA.value
    elif action == "recibir":
        movement = apply_movement(
            db,
            movement_type=MovementType.TRANSFER_IN,
            material=item.material,
            location_id=transfer.to_location_id,
            signed_qty=qty,
            user=user,
            document_type="stock_transfer",
            document_id=transfer.id,
            reference_code=transfer.number,
            notes=reason,
        )
        item.qty_received = as_qty(Decimal(str(item.qty_received)) + qty)
        discrepancy.status = DiscrepancyStatus.RECIBIDA.value
        discrepancy.movement_id = movement.id
    else:
        raise AppError(422, "La resolución tiene que ser devolver, registrar una pérdida o recibir el resto.")
    discrepancy.resolution_notes = reason
    discrepancy.resolved_by_user_id = user.id
    discrepancy.resolved_at = now_utc()
    db.flush()
    _refresh_transfer_status(db, transfer)
    audit(db, user, "RESOLVER_DIFERENCIA", "transfer_discrepancy", discrepancy.id, {"status": "PENDIENTE"}, {"status": discrepancy.status, "action": action}, reason)
    return discrepancy


def void_transfer(db: Session, transfer: StockTransfer, user: User, reason: str) -> StockTransfer:
    require_user(user)
    reason = require_reason(reason)
    if transfer.voided_at is not None:
        raise AppError(422, "La transferencia ya fue anulada.")
    before = {"status": transfer.status}
    movements = db.scalars(
        select(InventoryMovement).where(
            InventoryMovement.document_type == "stock_transfer",
            InventoryMovement.document_id == transfer.id,
            InventoryMovement.status == RecordStatus.CONFIRMADO.value,
        )
    ).all()
    for movement in movements:
        void_movement(db, movement, user, reason)
    for item in transfer.items:
        for row in db.scalars(select(TransferDiscrepancy).where(TransferDiscrepancy.transfer_item_id == item.id)).all():
            if row.status == DiscrepancyStatus.PENDIENTE.value:
                row.status = DiscrepancyStatus.DEVUELTA.value
                row.resolution_notes = reason
                row.resolved_by_user_id = user.id
                row.resolved_at = now_utc()
    transfer.status = TransferStatus.CANCELADA.value
    transfer.voided_by_user_id = user.id
    transfer.voided_at = now_utc()
    transfer.void_reason = reason
    db.flush()
    audit(db, user, "ANULAR_TRANSFERENCIA", "stock_transfer", transfer.id, before, {"status": transfer.status}, reason)
    return transfer
