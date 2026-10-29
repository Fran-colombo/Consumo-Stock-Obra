from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO, StringIO
import csv

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    GoodsReceipt,
    GoodsReceiptItem,
    InventoryMovement,
    Location,
    Material,
    MaterialConsumption,
    PurchaseOrder,
    PurchaseOrderItem,
    Rubric,
    StockBalance,
    StockTransfer,
    StockTransferItem,
    Task,
    TaskExecution,
    TheoreticalConsumptionLine,
    UnitOfMeasure,
    Work,
)
from app.models.enums import PurchaseOrderStatus, RecordStatus, TransferStatus
from app.services.calculations import deviation
from app.services.common import as_qty, period_bounds
from app.services.planning import executed_qty, projected_theoretical
from app.services.purchasing import net_received
from app.services.transfers import in_transit_qty


def _material_unit(db: Session, material: Material) -> str:
    unit = material.unit if material.unit else db.get(UnitOfMeasure, material.unit_id)
    return unit.code if unit else ""


def stock_rows(db: Session, material_id: int | None = None, location_id: int | None = None, q: str | None = None) -> list[dict]:
    balances = db.scalars(select(StockBalance)).all()
    keys = {(row.material_id, row.location_id) for row in balances}
    pending_map: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    orders = db.scalars(
        select(PurchaseOrder).where(
            PurchaseOrder.status.in_(
                [PurchaseOrderStatus.CONFIRMADA.value, PurchaseOrderStatus.PARCIAL.value, PurchaseOrderStatus.RECIBIDA.value]
            )
        )
    ).all()
    for order in orders:
        for item in order.items:
            pending = as_qty(Decimal(str(item.qty_ordered)) - net_received(db, item.id))
            if pending > 0:
                pending_map[(item.material_id, order.destination_location_id)] += pending
                keys.add((item.material_id, order.destination_location_id))
    transit_out: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    transit_in: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    transfers = db.scalars(
        select(StockTransfer).where(
            StockTransfer.status.in_([TransferStatus.EN_TRANSITO.value, TransferStatus.RECIBIDA_PARCIAL.value])
        )
    ).all()
    for transfer in transfers:
        for item in transfer.items:
            pending = in_transit_qty(db, item)
            if pending > 0:
                transit_out[(item.material_id, transfer.from_location_id)] += pending
                transit_in[(item.material_id, transfer.to_location_id)] += pending
                keys.add((item.material_id, transfer.from_location_id))
                keys.add((item.material_id, transfer.to_location_id))
    last_map: dict[tuple[int, int], InventoryMovement] = {}
    movements = db.scalars(
        select(InventoryMovement).where(InventoryMovement.status == RecordStatus.CONFIRMADO.value).order_by(InventoryMovement.occurred_at.asc())
    ).all()
    for movement in movements:
        last_map[(movement.material_id, movement.location_id)] = movement
        keys.add((movement.material_id, movement.location_id))
    balance_map = {(row.material_id, row.location_id): as_qty(row.on_hand) for row in balances}
    needle = (q or "").strip().lower()
    rows = []
    for mat_id, loc_id in sorted(keys):
        if material_id is not None and mat_id != material_id:
            continue
        if location_id is not None and loc_id != location_id:
            continue
        material = db.get(Material, mat_id)
        location = db.get(Location, loc_id)
        if material is None or location is None:
            continue
        if needle and needle not in material.name.lower() and needle not in material.code.lower() and needle not in location.name.lower():
            continue
        last = last_map.get((mat_id, loc_id))
        place = db.get(Work, location.work_id) if location.work_id else None
        rows.append(
            {
                "material_id": mat_id,
                "material_code": material.code,
                "material_name": material.name,
                "unit_code": _material_unit(db, material),
                "location_id": loc_id,
                "location_name": location.name,
                "location_code": location.code,
                "work_id": location.work_id,
                "work_name": place.name if place else None,
                "on_hand": as_qty(balance_map.get((mat_id, loc_id), Decimal("0"))),
                "pending_receipt": as_qty(pending_map.get((mat_id, loc_id), Decimal("0"))),
                "in_transit_out": as_qty(transit_out.get((mat_id, loc_id), Decimal("0"))),
                "in_transit_in": as_qty(transit_in.get((mat_id, loc_id), Decimal("0"))),
                "last_movement_at": last.occurred_at if last else None,
                "last_movement_type": last.movement_type if last else None,
                "last_movement_id": last.id if last else None,
            }
        )
    return rows


def comparison_rows(
    db: Session,
    work_id: int | None = None,
    rubric_id: int | None = None,
    task_id: int | None = None,
    material_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    start, end = period_bounds(date_from, date_to)
    theoretical: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    stmt = (
        select(TheoreticalConsumptionLine, TaskExecution)
        .join(TaskExecution, TaskExecution.id == TheoreticalConsumptionLine.task_execution_id)
        .where(TaskExecution.status == RecordStatus.CONFIRMADO.value)
    )
    if date_from is not None:
        stmt = stmt.where(TaskExecution.execution_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(TaskExecution.execution_date <= date_to)
    for line, execution in db.execute(stmt).all():
        theoretical[(execution.task_id, line.material_id)] += Decimal(str(line.output_qty))
    real: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    consumptions = select(MaterialConsumption).where(MaterialConsumption.status == RecordStatus.CONFIRMADO.value)
    if start is not None:
        consumptions = consumptions.where(MaterialConsumption.consumed_at >= start)
    if end is not None:
        consumptions = consumptions.where(MaterialConsumption.consumed_at <= end)
    for row in db.scalars(consumptions).all():
        sign = Decimal("-1") if row.corrects_consumption_id else Decimal("1")
        real[(row.task_id, row.material_id)] += sign * Decimal(str(row.quantity))
    keys = set(theoretical) | set(real)
    rows = []
    for key_task, key_material in keys:
        if task_id is not None and key_task != task_id:
            continue
        if material_id is not None and key_material != material_id:
            continue
        task = db.get(Task, key_task)
        material = db.get(Material, key_material)
        if task is None or material is None:
            continue
        if work_id is not None and task.work_id != work_id:
            continue
        if rubric_id is not None and task.rubric_id != rubric_id:
            continue
        work = db.get(Work, task.work_id)
        rubric = db.get(Rubric, task.rubric_id)
        executed = executed_qty(db, task.id, date_from, date_to)
        theo = as_qty(theoretical.get((key_task, key_material), Decimal("0")))
        real_qty = as_qty(real.get((key_task, key_material), Decimal("0")))
        gap = deviation(real_qty, theo)
        stock = _work_stock(db, task.work_id, material.id)
        purchased, received = _work_purchases(db, task.work_id, material.id, start, end)
        transferred_in, transferred_out = _work_transfers(db, task.work_id, material.id, start, end)
        rows.append(
            {
                "work_id": work.id,
                "work_name": work.name,
                "work_code": work.code,
                "rubric_id": rubric.id,
                "rubric_name": rubric.name,
                "task_id": task.id,
                "task_name": task.name,
                "material_id": material.id,
                "material_code": material.code,
                "material_name": material.name,
                "unit_code": _material_unit(db, material),
                "executed_qty": executed,
                "theoretical_qty": theo,
                "real_qty": real_qty,
                "absolute_difference": gap["absolute_difference"],
                "percent_deviation": gap["percent_deviation"],
                "percent_status": gap["percent_status"],
                "review_required": gap["review_required"],
                "stock_on_hand": stock,
                "purchased_qty": purchased,
                "received_qty": received,
                "transferred_in": transferred_in,
                "transferred_out": transferred_out,
            }
        )
    rows.sort(key=lambda row: (row["work_name"], row["rubric_name"], row["task_name"], row["material_name"]))
    return rows


def _work_location_ids(db: Session, work_id: int) -> list[int]:
    return list(db.scalars(select(Location.id).where(Location.work_id == work_id)).all())


def _work_stock(db: Session, work_id: int, material_id: int) -> Decimal:
    ids = _work_location_ids(db, work_id)
    if not ids:
        return Decimal("0.0000")
    total = db.scalar(
        select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
            StockBalance.material_id == material_id,
            StockBalance.location_id.in_(ids),
        )
    )
    return as_qty(total or 0)


def _work_purchases(db: Session, work_id: int, material_id: int, start: datetime | None, end: datetime | None) -> tuple[Decimal, Decimal]:
    orders = db.scalars(
        select(PurchaseOrder).where(
            PurchaseOrder.work_id == work_id,
            PurchaseOrder.status != PurchaseOrderStatus.CANCELADA.value,
            PurchaseOrder.status != PurchaseOrderStatus.BORRADOR.value,
        )
    ).all()
    purchased = Decimal("0")
    received = Decimal("0")
    for order in orders:
        if start is not None and order.created_at < start:
            if end is not None and order.created_at > end:
                continue
        in_period = True
        if start is not None and order.created_at < start:
            in_period = False
        if end is not None and order.created_at > end:
            in_period = False
        for item in order.items:
            if item.material_id != material_id:
                continue
            if in_period:
                purchased += Decimal(str(item.qty_ordered))
            receipt_items = db.scalars(
                select(GoodsReceiptItem)
                .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id)
                .where(
                    GoodsReceiptItem.purchase_order_item_id == item.id,
                    GoodsReceipt.status == RecordStatus.CONFIRMADO.value,
                )
            ).all()
            for receipt_item in receipt_items:
                moment = receipt_item.receipt.received_at
                if start is not None and moment < start:
                    continue
                if end is not None and moment > end:
                    continue
                sign = Decimal("-1") if receipt_item.receipt.corrects_receipt_id else Decimal("1")
                received += sign * Decimal(str(receipt_item.quantity))
    return as_qty(purchased), as_qty(received)


def _work_transfers(db: Session, work_id: int, material_id: int, start: datetime | None, end: datetime | None) -> tuple[Decimal, Decimal]:
    ids = _work_location_ids(db, work_id)
    if not ids:
        return Decimal("0.0000"), Decimal("0.0000")
    stmt = select(InventoryMovement).where(
        InventoryMovement.material_id == material_id,
        InventoryMovement.location_id.in_(ids),
        InventoryMovement.status == RecordStatus.CONFIRMADO.value,
        InventoryMovement.movement_type.in_(
            ["TRANSFERENCIA_ENTRADA", "TRANSFERENCIA_SALIDA", "TRANSFERENCIA_DEVOLUCION"]
        ),
    )
    if start is not None:
        stmt = stmt.where(InventoryMovement.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(InventoryMovement.occurred_at <= end)
    inbound = Decimal("0")
    outbound = Decimal("0")
    for movement in db.scalars(stmt).all():
        if movement.movement_type == "TRANSFERENCIA_SALIDA":
            outbound += abs(Decimal(str(movement.signed_qty)))
        elif movement.movement_type == "TRANSFERENCIA_ENTRADA":
            inbound += Decimal(str(movement.signed_qty))
        elif movement.movement_type == "TRANSFERENCIA_DEVOLUCION":
            inbound += Decimal(str(movement.signed_qty))
    return as_qty(inbound), as_qty(outbound)


def investigation(db: Session, task_id: int, material_id: int, date_from: date | None, date_to: date | None) -> dict:
    start, end = period_bounds(date_from, date_to)
    lines = []
    stmt = (
        select(TheoreticalConsumptionLine)
        .join(TaskExecution, TaskExecution.id == TheoreticalConsumptionLine.task_execution_id)
        .where(
            TaskExecution.task_id == task_id,
            TaskExecution.status == RecordStatus.CONFIRMADO.value,
            TheoreticalConsumptionLine.material_id == material_id,
        )
    )
    if date_from is not None:
        stmt = stmt.where(TaskExecution.execution_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(TaskExecution.execution_date <= date_to)
    for line in db.scalars(stmt).all():
        version = line.rule_version
        lines.append(
            {
                "execution_id": line.task_execution_id,
                "execution_date": line.execution.execution_date,
                "input_qty": line.input_qty,
                "coefficient": line.coefficient_snapshot,
                "factor": line.conversion_factor_snapshot,
                "output_qty": line.output_qty,
                "method": line.method_snapshot,
                "rule_version_id": line.rule_version_id,
                "rule_version": version.version if version else None,
                "valid_from": version.valid_from if version else None,
            }
        )
    consumptions = []
    cstmt = select(MaterialConsumption).where(
        MaterialConsumption.task_id == task_id,
        MaterialConsumption.material_id == material_id,
        MaterialConsumption.status == RecordStatus.CONFIRMADO.value,
    )
    if start is not None:
        cstmt = cstmt.where(MaterialConsumption.consumed_at >= start)
    if end is not None:
        cstmt = cstmt.where(MaterialConsumption.consumed_at <= end)
    for row in db.scalars(cstmt).all():
        consumptions.append(
            {
                "id": row.id,
                "quantity": row.quantity,
                "consumed_at": row.consumed_at,
                "location_id": row.location_id,
                "location_name": row.location.name,
                "corrects_consumption_id": row.corrects_consumption_id,
                "movement_id": row.movement_id,
                "recorded_by": row.recorded_by.full_name,
                "notes": row.notes,
            }
        )
    return {"theoretical_lines": lines, "consumptions": consumptions}


def dashboard(db: Session, work_id: int | None, date_from: date | None, date_to: date | None) -> dict:
    rows = comparison_rows(db, work_id=work_id, date_from=date_from, date_to=date_to)
    units = {row["unit_code"] for row in rows}
    comparable = len(units) <= 1
    if comparable:
        theoretical = as_qty(sum((row["theoretical_qty"] for row in rows), Decimal("0")))
        real = as_qty(sum((row["real_qty"] for row in rows), Decimal("0")))
        gap = deviation(real, theoretical)
        total_unit = next(iter(units)) if units else None
    else:
        theoretical = None
        real = None
        gap = {
            "absolute_difference": None,
            "percent_deviation": None,
            "percent_status": "NO_CALCULABLE",
            "review_required": False,
        }
        total_unit = None
    works_stmt = select(func.count()).select_from(Work).where(Work.status == "ACTIVA")
    if work_id is not None:
        works_stmt = works_stmt.where(Work.id == work_id)
    active_works = int(db.scalar(works_stmt) or 0)
    low_stock = []
    materials = db.scalars(select(Material).where(Material.reorder_point.is_not(None), Material.is_active.is_(True))).all()
    for material in materials:
        total = db.scalar(select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(StockBalance.material_id == material.id))
        total_q = as_qty(total or 0)
        if total_q <= Decimal(str(material.reorder_point)):
            low_stock.append(
                {
                    "material_id": material.id,
                    "material_name": material.name,
                    "material_code": material.code,
                    "unit_code": _material_unit(db, material),
                    "on_hand": total_q,
                    "reorder_point": as_qty(material.reorder_point),
                }
            )
    pending_orders = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.status.in_([PurchaseOrderStatus.CONFIRMADA.value, PurchaseOrderStatus.PARCIAL.value])
        )
    )
    in_transit = db.scalar(
        select(func.count()).select_from(StockTransfer).where(
            StockTransfer.status.in_([TransferStatus.EN_TRANSITO.value, TransferStatus.RECIBIDA_PARCIAL.value])
        )
    )
    by_work: dict[str, dict] = {}
    by_rubric: dict[str, dict] = {}
    for row in rows:
        bucket = by_work.setdefault(row["work_name"], {"theoretical": Decimal("0"), "real": Decimal("0")})
        bucket["theoretical"] += row["theoretical_qty"]
        bucket["real"] += row["real_qty"]
        rubric_bucket = by_rubric.setdefault(row["rubric_name"], {"theoretical": Decimal("0"), "real": Decimal("0")})
        rubric_bucket["theoretical"] += row["theoretical_qty"]
        rubric_bucket["real"] += row["real_qty"]
    top = sorted(rows, key=lambda row: abs(row["absolute_difference"]), reverse=True)[:8]
    top = [row for row in top if row["absolute_difference"] != 0]
    evolution = _evolution(rows, db, work_id, date_from, date_to)
    stock = stock_rows(db)
    by_location: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for item in stock:
        location = db.get(Location, item["location_id"])
        if work_id is not None and location is not None and location.work_id not in (None, work_id):
            continue
        by_location[item["location_name"]] += item["on_hand"]
    recent_stmt = select(InventoryMovement).where(InventoryMovement.status == RecordStatus.CONFIRMADO.value).order_by(InventoryMovement.occurred_at.desc()).limit(8)
    recent = []
    for movement in db.scalars(recent_stmt).all():
        recent.append(
            {
                "id": movement.id,
                "occurred_at": movement.occurred_at,
                "movement_type": movement.movement_type,
                "material_name": movement.material.name,
                "location_name": movement.location.name,
                "signed_qty": movement.signed_qty,
                "unit_code": _material_unit(db, movement.material),
                "reference_code": movement.reference_code,
                "recorded_by": movement.recorded_by.full_name,
            }
        )
    return {
        "active_works": active_works,
        "low_stock": low_stock,
        "pending_orders": int(pending_orders or 0),
        "transfers_in_transit": int(in_transit or 0),
        "comparable_totals": comparable,
        "total_unit": total_unit,
        "theoretical_qty": theoretical,
        "real_qty": real,
        "absolute_difference": gap["absolute_difference"],
        "percent_deviation": gap["percent_deviation"],
        "percent_status": gap["percent_status"],
        "review_required": gap["review_required"],
        "by_work": [{"name": name, "theoretical": as_qty(vals["theoretical"]), "real": as_qty(vals["real"])} for name, vals in by_work.items()],
        "by_rubric": [{"name": name, "theoretical": as_qty(vals["theoretical"]), "real": as_qty(vals["real"])} for name, vals in by_rubric.items()],
        "top_deviations": top,
        "evolution": evolution,
        "stock_by_location": [{"name": name, "on_hand": as_qty(qty)} for name, qty in by_location.items() if qty != 0],
        "recent_movements": recent,
    }


def _evolution(rows, db: Session, work_id: int | None, date_from: date | None, date_to: date | None) -> list[dict]:
    start, end = period_bounds(date_from, date_to)
    buckets: dict[str, dict] = defaultdict(lambda: {"theoretical": Decimal("0"), "real": Decimal("0")})
    stmt = (
        select(TheoreticalConsumptionLine, TaskExecution)
        .join(TaskExecution, TaskExecution.id == TheoreticalConsumptionLine.task_execution_id)
        .join(Task, Task.id == TaskExecution.task_id)
        .where(TaskExecution.status == RecordStatus.CONFIRMADO.value)
    )
    if work_id is not None:
        stmt = stmt.where(Task.work_id == work_id)
    if date_from is not None:
        stmt = stmt.where(TaskExecution.execution_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(TaskExecution.execution_date <= date_to)
    for line, execution in db.execute(stmt).all():
        key = execution.execution_date.strftime("%Y-%m")
        buckets[key]["theoretical"] += Decimal(str(line.output_qty))
    cstmt = (
        select(MaterialConsumption)
        .join(Task, Task.id == MaterialConsumption.task_id)
        .where(MaterialConsumption.status == RecordStatus.CONFIRMADO.value)
    )
    if work_id is not None:
        cstmt = cstmt.where(Task.work_id == work_id)
    if start is not None:
        cstmt = cstmt.where(MaterialConsumption.consumed_at >= start)
    if end is not None:
        cstmt = cstmt.where(MaterialConsumption.consumed_at <= end)
    from app.services.common import BA

    for row in db.scalars(cstmt).all():
        local = row.consumed_at.astimezone(BA)
        key = local.strftime("%Y-%m")
        sign = Decimal("-1") if row.corrects_consumption_id else Decimal("1")
        buckets[key]["real"] += sign * Decimal(str(row.quantity))
    return [
        {"period": key, "theoretical": as_qty(value["theoretical"]), "real": as_qty(value["real"])}
        for key, value in sorted(buckets.items())
    ]


def task_theoretical_view(db: Session, task: Task) -> dict:
    totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    lines = db.scalars(
        select(TheoreticalConsumptionLine)
        .join(TaskExecution, TaskExecution.id == TheoreticalConsumptionLine.task_execution_id)
        .where(TaskExecution.task_id == task.id, TaskExecution.status == RecordStatus.CONFIRMADO.value)
    ).all()
    for line in lines:
        totals[line.material_id] += Decimal(str(line.output_qty))
    materials = []
    for mat_id, qty in totals.items():
        material = db.get(Material, mat_id)
        materials.append(
            {
                "material_id": mat_id,
                "material_name": material.name,
                "material_code": material.code,
                "unit_code": _material_unit(db, material),
                "theoretical_qty": as_qty(qty),
            }
        )
    return {
        "task_id": task.id,
        "executed_qty": executed_qty(db, task.id),
        "planned_qty": task.planned_qty,
        "materials": materials,
        "projection": projected_theoretical(db, task),
    }


def movements_query(db: Session, material_id: int | None, location_id: int | None, movement_type: str | None, date_from: date | None, date_to: date | None, q: str | None):
    start, end = period_bounds(date_from, date_to)
    stmt = select(InventoryMovement).order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
    if material_id is not None:
        stmt = stmt.where(InventoryMovement.material_id == material_id)
    if location_id is not None:
        stmt = stmt.where(InventoryMovement.location_id == location_id)
    if movement_type:
        stmt = stmt.where(InventoryMovement.movement_type == movement_type)
    if start is not None:
        stmt = stmt.where(InventoryMovement.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(InventoryMovement.occurred_at <= end)
    rows = db.scalars(stmt).all()
    needle = (q or "").strip().lower()
    if needle:
        rows = [
            row
            for row in rows
            if needle in row.material.name.lower()
            or needle in (row.reference_code or "").lower()
            or needle in row.location.name.lower()
        ]
    return rows


def purchase_report_rows(db: Session, work_id: int | None = None) -> list[dict]:
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    if work_id is not None:
        stmt = stmt.where(PurchaseOrder.work_id == work_id)
    result = []
    for order in db.scalars(stmt).all():
        for item in order.items:
            received = net_received(db, item.id)
            pending = as_qty(Decimal(str(item.qty_ordered)) - received)
            if pending < 0:
                pending = Decimal("0.0000")
            result.append(
                {
                    "number": order.number,
                    "supplier": order.supplier.name,
                    "work": order.work.name if order.work else "",
                    "destination": order.destination.name,
                    "date": order.created_at,
                    "material": item.material.name,
                    "unit": item.unit.code,
                    "qty_ordered": as_qty(item.qty_ordered),
                    "qty_received": received,
                    "qty_pending": pending,
                    "status": order.status,
                }
            )
    return result


def rows_to_csv(headers: list[str], rows: list[list]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def rows_to_xlsx(headers: list[str], rows: list[list], title: str) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = title[:31]
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()
