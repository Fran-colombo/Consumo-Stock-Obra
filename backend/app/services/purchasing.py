from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import (
    GoodsReceipt,
    GoodsReceiptItem,
    Location,
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    UnitOfMeasure,
    User,
    Work,
)
from app.models.enums import MovementType, PurchaseOrderStatus, RecordStatus
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
    setting_bool,
)
from app.services.stock import apply_movement, rebuild_balance, void_movement


def create_supplier(db: Session, user: User, name: str, contact: str | None) -> Supplier:
    require_user(user)
    if not name.strip():
        raise AppError(422, "El nombre del proveedor es obligatorio.")
    supplier = Supplier(name=name.strip(), contact=(contact or "").strip() or None, is_active=True, created_at=now_utc())
    db.add(supplier)
    db.flush()
    return supplier


def update_supplier(db: Session, supplier: Supplier, data: dict) -> Supplier:
    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise AppError(422, "El nombre del proveedor es obligatorio.")
        supplier.name = str(data["name"]).strip()
    if "contact" in data:
        supplier.contact = (data["contact"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        supplier.is_active = data["is_active"]
    db.flush()
    return supplier


def _price_pair(unit_price: Decimal | None, currency: str | None, unit: UnitOfMeasure) -> tuple[Decimal | None, str | None]:
    if unit_price is None and not currency:
        return None, None
    if unit_price is None or not currency:
        raise AppError(422, "Si registrás un precio, indicá también la moneda.")
    price = as_qty(unit_price)
    if price < 0:
        raise AppError(422, "El precio no puede ser negativo.")
    assert_precision(price, 4, "El precio")
    code = currency.strip().upper()
    if len(code) < 3 or len(code) > 8:
        raise AppError(422, "La moneda tiene que identificarse con un código, por ejemplo ARS.")
    return price, code


def _validate_item(db: Session, material_id: int, quantity: Decimal, unit_price: Decimal | None, currency: str | None):
    material = get_or_404(db, Material, material_id, "el material")
    ensure_active(material, "El material")
    unit = db.get(UnitOfMeasure, material.unit_id)
    qty = as_qty(quantity)
    assert_positive(qty, "La cantidad solicitada")
    assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad solicitada")
    price, curr = _price_pair(unit_price, currency, unit)
    return material, qty, price, curr


def create_purchase_order(
    db: Session,
    user: User,
    supplier_id: int,
    destination_location_id: int,
    work_id: int | None,
    expected_date: date | None,
    notes: str | None,
    items: list[dict],
) -> PurchaseOrder:
    require_user(user)
    supplier = get_or_404(db, Supplier, supplier_id, "el proveedor")
    ensure_active(supplier, "El proveedor")
    destination = get_or_404(db, Location, destination_location_id, "la ubicación de destino")
    ensure_active(destination, "La ubicación")
    if work_id is not None:
        get_or_404(db, Work, work_id, "la obra")
    if not items:
        raise AppError(422, "La orden tiene que incluir al menos un material.")
    order = PurchaseOrder(
        number=next_number(db, "OC"),
        supplier_id=supplier.id,
        work_id=work_id,
        destination_location_id=destination.id,
        status=PurchaseOrderStatus.BORRADOR.value,
        expected_date=expected_date,
        notes=(notes or "").strip() or None,
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(order)
    db.flush()
    seen: set[int] = set()
    for raw in items:
        material, qty, price, curr = _validate_item(db, raw["material_id"], raw["quantity"], raw.get("unit_price"), raw.get("currency"))
        if material.id in seen:
            raise AppError(422, f"El material {material.name} está repetido en la orden.")
        seen.add(material.id)
        db.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                material_id=material.id,
                qty_ordered=qty,
                unit_id=material.unit_id,
                unit_price=price,
                currency=curr,
            )
        )
    db.flush()
    audit(db, user, "CREAR_ORDEN", "purchase_order", order.id, None, {"number": order.number, "status": order.status})
    return order


def update_purchase_order(db: Session, order: PurchaseOrder, user: User, data: dict) -> PurchaseOrder:
    require_user(user)
    if order.status == PurchaseOrderStatus.CANCELADA.value:
        raise AppError(422, "La orden cancelada no se puede modificar.")
    if "supplier_id" in data and data["supplier_id"] is not None:
        supplier = get_or_404(db, Supplier, data["supplier_id"], "el proveedor")
        ensure_active(supplier, "El proveedor")
        order.supplier_id = supplier.id
    if "destination_location_id" in data and data["destination_location_id"] is not None:
        destination = get_or_404(db, Location, data["destination_location_id"], "la ubicación")
        ensure_active(destination, "La ubicación")
        order.destination_location_id = destination.id
    if "work_id" in data:
        if data["work_id"] is not None:
            get_or_404(db, Work, data["work_id"], "la obra")
        order.work_id = data["work_id"]
    if "expected_date" in data:
        order.expected_date = data["expected_date"]
    if "notes" in data:
        order.notes = (data["notes"] or "").strip() or None
    if "items" in data and data["items"] is not None:
        if order.status != PurchaseOrderStatus.BORRADOR.value:
            raise AppError(422, "Los ítems se reemplazan solo mientras la orden está en borrador.")
        for item in list(order.items):
            db.delete(item)
        db.flush()
        seen: set[int] = set()
        for raw in data["items"]:
            material, qty, price, curr = _validate_item(db, raw["material_id"], raw["quantity"], raw.get("unit_price"), raw.get("currency"))
            if material.id in seen:
                raise AppError(422, f"El material {material.name} está repetido en la orden.")
            seen.add(material.id)
            db.add(
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    material_id=material.id,
                    qty_ordered=qty,
                    unit_id=material.unit_id,
                    unit_price=price,
                    currency=curr,
                )
            )
    db.flush()
    return order


def confirm_purchase_order(db: Session, order: PurchaseOrder, user: User) -> PurchaseOrder:
    require_user(user)
    if order.status != PurchaseOrderStatus.BORRADOR.value:
        raise AppError(422, "Solo se puede confirmar una orden en borrador.")
    if not order.items:
        raise AppError(422, "La orden no tiene materiales.")
    order.status = PurchaseOrderStatus.CONFIRMADA.value
    db.flush()
    audit(db, user, "CONFIRMAR_ORDEN", "purchase_order", order.id, {"status": "BORRADOR"}, {"status": order.status})
    return order


def net_received(db: Session, item_id: int) -> Decimal:
    rows = db.scalars(
        select(GoodsReceiptItem)
        .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id)
        .where(
            GoodsReceiptItem.purchase_order_item_id == item_id,
            GoodsReceipt.status == RecordStatus.CONFIRMADO.value,
        )
    ).all()
    total = Decimal("0")
    for row in rows:
        if row.receipt.corrects_receipt_id:
            total -= Decimal(str(row.quantity))
        else:
            total += Decimal(str(row.quantity))
    return as_qty(total)


def refresh_order_status(db: Session, order: PurchaseOrder) -> None:
    if order.status in (PurchaseOrderStatus.BORRADOR.value, PurchaseOrderStatus.CANCELADA.value):
        return
    received_any = False
    pending_any = False
    for item in order.items:
        net = net_received(db, item.id)
        if net > 0:
            received_any = True
        if net < Decimal(str(item.qty_ordered)):
            pending_any = True
    if not received_any:
        order.status = PurchaseOrderStatus.CONFIRMADA.value
    elif pending_any:
        order.status = PurchaseOrderStatus.PARCIAL.value
    else:
        order.status = PurchaseOrderStatus.RECIBIDA.value
    db.flush()


def cancel_purchase_order(db: Session, order: PurchaseOrder, user: User, reason: str) -> PurchaseOrder:
    require_user(user)
    reason = require_reason(reason)
    if order.status == PurchaseOrderStatus.CANCELADA.value:
        raise AppError(422, "La orden ya está cancelada.")
    for item in order.items:
        if net_received(db, item.id) > 0:
            raise AppError(422, "Hay recepciones confirmadas. Corregí o anulá esas recepciones antes de cancelar la orden.")
    before = order.status
    order.status = PurchaseOrderStatus.CANCELADA.value
    db.flush()
    audit(db, user, "CANCELAR_ORDEN", "purchase_order", order.id, {"status": before}, {"status": order.status}, reason)
    return order


def change_ordered_qty(db: Session, item: PurchaseOrderItem, user: User, quantity: Decimal, reason: str | None) -> PurchaseOrderItem:
    require_user(user)
    order = item.order
    if order.status == PurchaseOrderStatus.CANCELADA.value:
        raise AppError(422, "La orden cancelada no se puede modificar.")
    unit = db.get(UnitOfMeasure, item.unit_id)
    qty = as_qty(quantity)
    assert_positive(qty, "La cantidad solicitada")
    assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad solicitada")
    received = net_received(db, item.id)
    if qty < received:
        raise AppError(422, "La cantidad pedida no puede ser menor que lo ya recibido.")
    before = str(item.qty_ordered)
    item.qty_ordered = qty
    db.flush()
    if order.status != PurchaseOrderStatus.BORRADOR.value:
        refresh_order_status(db, order)
        audit(db, user, "CAMBIAR_CANTIDAD_ORDEN", "purchase_order_item", item.id, {"qty_ordered": before}, {"qty_ordered": str(qty)}, require_reason(reason))
    return item


def _receipt_items_payload(db: Session, order: PurchaseOrder, raw_items: list[dict]) -> list[tuple[PurchaseOrderItem, Decimal]]:
    if not raw_items:
        raise AppError(422, "Indicá al menos un material recibido.")
    prepared = []
    seen: set[int] = set()
    for raw in raw_items:
        po_item = get_or_404(db, PurchaseOrderItem, raw["purchase_order_item_id"], "el ítem de la orden")
        if po_item.purchase_order_id != order.id:
            raise AppError(422, "El material no pertenece a la orden seleccionada.")
        if po_item.id in seen:
            raise AppError(422, "Hay un material repetido en la recepción.")
        seen.add(po_item.id)
        unit = db.get(UnitOfMeasure, po_item.unit_id)
        qty = as_qty(raw["quantity"])
        assert_positive(qty, "La cantidad recibida")
        assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad recibida")
        prepared.append((po_item, qty))
    return prepared


def register_receipt(
    db: Session,
    user: User,
    order: PurchaseOrder,
    location_id: int,
    raw_items: list[dict],
    received_at: datetime | None,
    notes: str | None,
) -> GoodsReceipt:
    require_user(user)
    if order.status not in (
        PurchaseOrderStatus.CONFIRMADA.value,
        PurchaseOrderStatus.PARCIAL.value,
        PurchaseOrderStatus.RECIBIDA.value,
    ):
        raise AppError(422, "Confirmá la orden antes de registrar una recepción.")
    location = get_or_404(db, Location, location_id, "la ubicación")
    ensure_active(location, "La ubicación")
    prepared = _receipt_items_payload(db, order, raw_items)
    allow_over = setting_bool(db, "allow_over_receipt")
    checked = []
    for po_item, qty in prepared:
        pending = as_qty(Decimal(str(po_item.qty_ordered)) - net_received(db, po_item.id))
        excedente = qty > pending
        if excedente and not allow_over:
            raise AppError(422, f"La cantidad de {po_item.material.name} supera lo pendiente de la orden.")
        checked.append((po_item, qty, excedente))
    when = received_at or now_utc()
    receipt = GoodsReceipt(
        purchase_order_id=order.id,
        location_id=location.id,
        received_by_user_id=user.id,
        received_at=when,
        notes=(notes or "").strip() or None,
        status=RecordStatus.CONFIRMADO.value,
        corrects_receipt_id=None,
        created_at=now_utc(),
    )
    db.add(receipt)
    db.flush()
    for po_item, qty, excedente in checked:
        material = po_item.material
        movement = apply_movement(
            db,
            movement_type=MovementType.GOODS_RECEIPT,
            material=material,
            location_id=location.id,
            signed_qty=qty,
            user=user,
            document_type="goods_receipt",
            document_id=receipt.id,
            reference_code=order.number,
            notes=notes,
            occurred_at=when,
        )
        db.add(
            GoodsReceiptItem(
                goods_receipt_id=receipt.id,
                purchase_order_item_id=po_item.id,
                material_id=material.id,
                quantity=qty,
                unit_id=material.unit_id,
                excedente=excedente,
                movement_id=movement.id,
            )
        )
    db.flush()
    refresh_order_status(db, order)
    audit(db, user, "REGISTRAR_RECEPCION", "goods_receipt", receipt.id, None, {"order": order.number, "location_id": location.id})
    return receipt


def correct_receipt(
    db: Session,
    user: User,
    receipt: GoodsReceipt,
    raw_items: list[dict],
    reason: str,
    when: datetime | None,
) -> GoodsReceipt:
    require_user(user)
    reason = require_reason(reason)
    if receipt.status != RecordStatus.CONFIRMADO.value or receipt.corrects_receipt_id is not None:
        raise AppError(422, "La corrección se registra sobre una recepción confirmada.")
    order = receipt.order
    prepared = _receipt_items_payload(db, order, raw_items)
    original_by_item = {item.purchase_order_item_id: item for item in receipt.items}
    reversal = GoodsReceipt(
        purchase_order_id=order.id,
        location_id=receipt.location_id,
        received_by_user_id=user.id,
        received_at=when or now_utc(),
        notes=reason,
        status=RecordStatus.CONFIRMADO.value,
        corrects_receipt_id=receipt.id,
        created_at=now_utc(),
    )
    db.add(reversal)
    db.flush()
    for po_item, qty in prepared:
        original = original_by_item.get(po_item.id)
        if original is None:
            raise AppError(422, "La corrección tiene que referirse a materiales de esa recepción.")
        already = db.scalar(
            select(func.coalesce(func.sum(GoodsReceiptItem.quantity), 0))
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id)
            .where(
                GoodsReceipt.corrects_receipt_id == receipt.id,
                GoodsReceipt.status == RecordStatus.CONFIRMADO.value,
                GoodsReceiptItem.purchase_order_item_id == po_item.id,
            )
        )
        remaining = as_qty(Decimal(str(original.quantity)) - Decimal(str(already or 0)))
        if qty > remaining:
            raise AppError(422, f"La corrección de {po_item.material.name} supera lo recibido en esa entrega.")
        movement = apply_movement(
            db,
            movement_type=MovementType.RECEIPT_REVERSAL,
            material=po_item.material,
            location_id=receipt.location_id,
            signed_qty=-qty,
            user=user,
            document_type="goods_receipt",
            document_id=reversal.id,
            reference_code=order.number,
            notes=reason,
            occurred_at=reversal.received_at,
            corrects_movement_id=original.movement_id,
        )
        db.add(
            GoodsReceiptItem(
                goods_receipt_id=reversal.id,
                purchase_order_item_id=po_item.id,
                material_id=po_item.material_id,
                quantity=qty,
                unit_id=po_item.unit_id,
                excedente=False,
                movement_id=movement.id,
            )
        )
    db.flush()
    refresh_order_status(db, order)
    audit(db, user, "CORREGIR_RECEPCION", "goods_receipt", reversal.id, {"receipt_id": receipt.id}, {"quantities": [str(qty) for _, qty in prepared]}, reason)
    return reversal


def void_receipt(db: Session, receipt: GoodsReceipt, user: User, reason: str) -> GoodsReceipt:
    require_user(user)
    reason = require_reason(reason)
    if receipt.status == RecordStatus.ANULADO.value:
        raise AppError(422, "La recepción ya está anulada.")
    children = db.scalar(
        select(func.count()).select_from(GoodsReceipt).where(
            GoodsReceipt.corrects_receipt_id == receipt.id,
            GoodsReceipt.status == RecordStatus.CONFIRMADO.value,
        )
    )
    if children:
        raise AppError(422, "Anulá primero las correcciones de esta recepción.")
    before = {"status": receipt.status, "items": [{"id": item.id, "quantity": str(item.quantity)} for item in receipt.items]}
    for item in receipt.items:
        if item.movement_id:
            movement = db.get(item.movement.__class__, item.movement_id)
            from app.models.entities import InventoryMovement

            movement = db.get(InventoryMovement, item.movement_id)
            if movement and movement.status == RecordStatus.CONFIRMADO.value:
                void_movement(db, movement, user, reason)
    receipt.status = RecordStatus.ANULADO.value
    receipt.voided_by_user_id = user.id
    receipt.voided_at = now_utc()
    receipt.void_reason = reason
    db.flush()
    refresh_order_status(db, receipt.order)
    audit(db, user, "ANULAR_RECEPCION", "goods_receipt", receipt.id, before, {"status": receipt.status}, reason)
    return receipt


def edit_receipt_item(db: Session, item: GoodsReceiptItem, user: User, quantity: Decimal, reason: str) -> GoodsReceiptItem:
    require_user(user)
    reason = require_reason(reason)
    receipt = item.receipt
    if receipt.status != RecordStatus.CONFIRMADO.value or receipt.corrects_receipt_id is not None:
        raise AppError(422, "Solo el administrador puede corregir la cantidad de una recepción confirmada, y no sobre una reversa.")
    unit = db.get(UnitOfMeasure, item.unit_id)
    qty = as_qty(quantity)
    assert_positive(qty, "La cantidad recibida")
    assert_precision(qty, unit.decimal_places if unit else 4, "La cantidad recibida")
    from app.models.entities import InventoryMovement

    movement = db.get(InventoryMovement, item.movement_id)
    before_qty = Decimal(str(item.quantity))
    current_net = net_received(db, item.purchase_order_item_id)
    item.quantity = qty
    others = as_qty(current_net - before_qty + qty)
    ordered = Decimal(str(item.order_item.qty_ordered))
    excedente = others > ordered
    if excedente and not setting_bool(db, "allow_over_receipt"):
        raise AppError(422, "La cantidad supera lo pedido y la recepción por encima de la orden está desactivada.")
    item.excedente = excedente
    movement.signed_qty = qty
    rebuild_balance(db, item.material_id, receipt.location_id)
    db.flush()
    refresh_order_status(db, receipt.order)
    audit(db, user, "CORREGIR_RECEPCION", "goods_receipt_item", item.id, {"quantity": str(before_qty)}, {"quantity": str(qty)}, reason)
    return item
