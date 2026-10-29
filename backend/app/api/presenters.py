from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ConsumptionRule,
    ConsumptionRuleVersion,
    GoodsReceipt,
    InventoryAdjustment,
    InventoryMovement,
    Location,
    Material,
    MaterialConsumption,
    MaterialUnitConversion,
    PurchaseOrder,
    PurchaseOrderItem,
    Rubric,
    StockTransfer,
    Supplier,
    Task,
    TaskExecution,
    TransferDiscrepancy,
    UnitOfMeasure,
    User,
    Work,
)
from app.services.common import as_qty, user_brief
from app.services.planning import current_version, executed_qty
from app.services.purchasing import net_received
from app.services.transfers import discrepancy_qty, in_transit_qty


def _iso(value: datetime | date | None):
    return value.isoformat() if value is not None else None


def _qty(value: Decimal | None):
    if value is None:
        return None
    return format(as_qty(value), "f")


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": _iso(user.created_at),
    }


def unit_out(unit: UnitOfMeasure) -> dict:
    return {"id": unit.id, "code": unit.code, "name": unit.name, "decimal_places": unit.decimal_places}


def work_out(db: Session, work: Work) -> dict:
    location = db.scalar(select(Location).where(Location.work_id == work.id).order_by(Location.id.asc()))
    return {
        "id": work.id,
        "name": work.name,
        "code": work.code,
        "address": work.address,
        "status": work.status,
        "start_date": _iso(work.start_date),
        "notes": work.notes,
        "created_at": _iso(work.created_at),
        "location_id": location.id if location else None,
        "location_name": location.name if location else None,
    }


def location_out(db: Session, location: Location) -> dict:
    work = db.get(Work, location.work_id) if location.work_id else None
    return {
        "id": location.id,
        "name": location.name,
        "code": location.code,
        "location_type": location.location_type,
        "work_id": location.work_id,
        "work_name": work.name if work else None,
        "is_active": location.is_active,
    }


def rubric_out(rubric: Rubric) -> dict:
    return {
        "id": rubric.id,
        "name": rubric.name,
        "code": rubric.code,
        "description": rubric.description,
        "is_active": rubric.is_active,
    }


def material_out(db: Session, material: Material) -> dict:
    unit = db.get(UnitOfMeasure, material.unit_id)
    return {
        "id": material.id,
        "code": material.code,
        "name": material.name,
        "category": material.category,
        "unit_id": material.unit_id,
        "unit_code": unit.code if unit else None,
        "unit_name": unit.name if unit else None,
        "description": material.description,
        "is_active": material.is_active,
        "notes": material.notes,
        "reorder_point": _qty(material.reorder_point),
    }


def task_out(db: Session, task: Task) -> dict:
    unit = db.get(UnitOfMeasure, task.unit_id)
    rubric = db.get(Rubric, task.rubric_id)
    return {
        "id": task.id,
        "work_id": task.work_id,
        "rubric_id": task.rubric_id,
        "rubric_name": rubric.name if rubric else None,
        "name": task.name,
        "description": task.description,
        "unit_id": task.unit_id,
        "unit_code": unit.code if unit else None,
        "unit_name": unit.name if unit else None,
        "planned_qty": _qty(task.planned_qty),
        "executed_qty": _qty(executed_qty(db, task.id)),
        "execution_start": _iso(task.execution_start),
        "execution_end": _iso(task.execution_end),
        "status": task.status,
        "notes": task.notes,
    }


def _version_out(db: Session, version: ConsumptionRuleVersion | None) -> dict | None:
    if version is None:
        return None
    ref = db.get(UnitOfMeasure, version.reference_unit_id)
    out = db.get(UnitOfMeasure, version.output_unit_id)
    return {
        "id": version.id,
        "version": version.version,
        "method": version.method,
        "coefficient": _qty(version.coefficient),
        "reference_unit_code": ref.code if ref else None,
        "output_unit_code": out.code if out else None,
        "output_unit_id": version.output_unit_id,
        "valid_from": _iso(version.valid_from),
        "valid_to": _iso(version.valid_to),
        "change_reason": version.change_reason,
    }


def rule_out(db: Session, rule: ConsumptionRule) -> dict:
    material = db.get(Material, rule.material_id)
    unit = db.get(UnitOfMeasure, material.unit_id) if material else None
    return {
        "id": rule.id,
        "task_id": rule.task_id,
        "material_id": rule.material_id,
        "material_name": material.name if material else None,
        "material_code": material.code if material else None,
        "unit_code": unit.code if unit else None,
        "is_active": rule.is_active,
        "current": _version_out(db, current_version(db, rule)),
        "versions": [_version_out(db, version) for version in sorted(rule.versions, key=lambda item: item.version)],
    }


def execution_out(db: Session, execution: TaskExecution) -> dict:
    user = db.get(User, execution.recorded_by_user_id)
    return {
        "id": execution.id,
        "task_id": execution.task_id,
        "quantity_delta": _qty(execution.quantity_delta),
        "execution_date": _iso(execution.execution_date),
        "notes": execution.notes,
        "status": execution.status,
        "corrects_execution_id": execution.corrects_execution_id,
        "recorded_by": user.full_name if user else None,
        "void_reason": execution.void_reason,
        "lines": [
            {
                "material_id": line.material_id,
                "material_name": line.material.name,
                "coefficient": _qty(line.coefficient_snapshot),
                "method": line.method_snapshot,
                "input_qty": _qty(line.input_qty),
                "output_qty": _qty(line.output_qty),
                "factor": _qty(line.conversion_factor_snapshot),
                "rule_version_id": line.rule_version_id,
                "unit_code": line.material.unit.code,
            }
            for line in execution.lines
        ],
    }


def order_out(db: Session, order: PurchaseOrder) -> dict:
    items = []
    for item in order.items:
        received = net_received(db, item.id)
        pending = as_qty(Decimal(str(item.qty_ordered)) - received)
        items.append(
            {
                "id": item.id,
                "material_id": item.material_id,
                "material_name": item.material.name,
                "material_code": item.material.code,
                "unit_code": item.unit.code,
                "qty_ordered": _qty(item.qty_ordered),
                "qty_received": _qty(received),
                "qty_pending": _qty(pending if pending > 0 else Decimal("0")),
                "unit_price": _qty(item.unit_price),
                "currency": item.currency,
            }
        )
    return {
        "id": order.id,
        "number": order.number,
        "supplier_id": order.supplier_id,
        "supplier_name": order.supplier.name,
        "work_id": order.work_id,
        "work_name": order.work.name if order.work else None,
        "destination_location_id": order.destination_location_id,
        "destination_name": order.destination.name,
        "status": order.status,
        "expected_date": _iso(order.expected_date),
        "notes": order.notes,
        "created_at": _iso(order.created_at),
        "created_by": order.created_by.full_name,
        "items": items,
    }


def receipt_out(receipt: GoodsReceipt) -> dict:
    return {
        "id": receipt.id,
        "purchase_order_id": receipt.purchase_order_id,
        "order_number": receipt.order.number,
        "location_id": receipt.location_id,
        "location_name": receipt.location.name,
        "received_at": _iso(receipt.received_at),
        "received_by": receipt.received_by.full_name,
        "notes": receipt.notes,
        "status": receipt.status,
        "corrects_receipt_id": receipt.corrects_receipt_id,
        "void_reason": receipt.void_reason,
        "items": [
            {
                "id": item.id,
                "purchase_order_item_id": item.purchase_order_item_id,
                "material_id": item.material_id,
                "material_name": item.material.name,
                "quantity": _qty(item.quantity),
                "excedente": item.excedente,
                "movement_id": item.movement_id,
            }
            for item in receipt.items
        ],
    }


def consumption_out(row: MaterialConsumption) -> dict:
    return {
        "id": row.id,
        "work_id": row.work_id,
        "work_name": row.work.name,
        "task_id": row.task_id,
        "task_name": row.task.name,
        "rubric_id": row.task.rubric_id,
        "rubric_name": row.task.rubric.name,
        "location_id": row.location_id,
        "location_name": row.location.name,
        "material_id": row.material_id,
        "material_name": row.material.name,
        "material_code": row.material.code,
        "quantity": _qty(row.quantity),
        "unit_code": row.material.unit.code,
        "consumed_at": _iso(row.consumed_at),
        "recorded_by": row.recorded_by.full_name,
        "notes": row.notes,
        "status": row.status,
        "corrects_consumption_id": row.corrects_consumption_id,
        "movement_id": row.movement_id,
        "void_reason": row.void_reason,
    }


def transfer_out(db: Session, transfer: StockTransfer) -> dict:
    items = []
    for item in transfer.items:
        discrepancies = db.scalars(
            select(TransferDiscrepancy).where(TransferDiscrepancy.transfer_item_id == item.id)
        ).all()
        items.append(
            {
                "id": item.id,
                "material_id": item.material_id,
                "material_name": item.material.name,
                "material_code": item.material.code,
                "unit_code": item.unit.code,
                "qty_sent": _qty(item.qty_sent),
                "qty_received": _qty(item.qty_received),
                "qty_returned": _qty(item.qty_returned),
                "in_transit": _qty(in_transit_qty(db, item)),
                "discrepancy_qty": _qty(discrepancy_qty(db, item.id)),
                "discrepancies": [
                    {
                        "id": row.id,
                        "quantity": _qty(row.quantity),
                        "status": row.status,
                        "resolution_notes": row.resolution_notes,
                    }
                    for row in discrepancies
                ],
            }
        )
    return {
        "id": transfer.id,
        "number": transfer.number,
        "from_location_id": transfer.from_location_id,
        "from_location_name": transfer.origin.name,
        "to_location_id": transfer.to_location_id,
        "to_location_name": transfer.destination.name,
        "status": transfer.status,
        "notes": transfer.notes,
        "created_at": _iso(transfer.created_at),
        "created_by": transfer.created_by.full_name,
        "authorized_by": user_brief(db.get(User, transfer.authorized_by_user_id)) if transfer.authorized_by_user_id else None,
        "authorized_operational_name": transfer.authorized_operational_name,
        "authorized_at": _iso(transfer.authorized_at),
        "executed_by": user_brief(db.get(User, transfer.executed_by_user_id)) if transfer.executed_by_user_id else None,
        "executed_operational_name": transfer.executed_operational_name,
        "executed_at": _iso(transfer.executed_at),
        "received_by": user_brief(db.get(User, transfer.received_by_user_id)) if transfer.received_by_user_id else None,
        "received_operational_name": transfer.received_operational_name,
        "received_at": _iso(transfer.received_at),
        "void_reason": transfer.void_reason,
        "items": items,
    }


def movement_out(movement: InventoryMovement) -> dict:
    return {
        "id": movement.id,
        "movement_type": movement.movement_type,
        "material_id": movement.material_id,
        "material_name": movement.material.name,
        "material_code": movement.material.code,
        "location_id": movement.location_id,
        "location_name": movement.location.name,
        "signed_qty": _qty(movement.signed_qty),
        "unit_code": movement.material.unit.code,
        "occurred_at": _iso(movement.occurred_at),
        "recorded_by": movement.recorded_by.full_name,
        "document_type": movement.document_type,
        "document_id": movement.document_id,
        "reference_code": movement.reference_code,
        "notes": movement.notes,
        "status": movement.status,
        "corrects_movement_id": movement.corrects_movement_id,
        "void_reason": movement.void_reason,
    }


def adjustment_out(row: InventoryAdjustment) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "material_name": row.material.name,
        "location_id": row.location_id,
        "location_name": row.location.name,
        "previous_qty": _qty(row.previous_qty),
        "counted_qty": _qty(row.counted_qty),
        "difference": _qty(row.difference),
        "reason": row.reason,
        "occurred_at": _iso(row.occurred_at),
        "recorded_by": row.recorded_by.full_name,
        "status": row.status,
        "movement_id": row.movement_id,
        "void_reason": row.void_reason,
    }


def supplier_out(supplier: Supplier) -> dict:
    return {"id": supplier.id, "name": supplier.name, "contact": supplier.contact, "is_active": supplier.is_active}


def conversion_out(row: MaterialUnitConversion) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "material_name": row.material.name,
        "from_unit_id": row.from_unit_id,
        "from_unit_code": row.from_unit.code,
        "to_unit_id": row.to_unit_id,
        "to_unit_code": row.to_unit.code,
        "factor": _qty(row.factor),
        "notes": row.notes,
    }


def page(items: list, total: int, page_number: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page_number, "page_size": page_size}


def paginate(rows: list, page_number: int, page_size: int) -> dict:
    page_number = max(page_number, 1)
    page_size = min(max(page_size, 1), 100)
    start = (page_number - 1) * page_size
    return page(rows[start : start + page_size], len(rows), page_number, page_size)
