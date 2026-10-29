from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import (
    ConsumptionRule,
    ConsumptionRuleVersion,
    Location,
    Material,
    MaterialUnitConversion,
    Rubric,
    Task,
    TaskExecution,
    TheoreticalConsumptionLine,
    UnitOfMeasure,
    User,
    Work,
)
from app.models.enums import CalcMethod, LocationType, RecordStatus
from app.services.calculations import coefficient_output
from app.services.common import (
    as_qty,
    assert_non_negative,
    assert_positive,
    assert_precision,
    audit,
    ensure_active,
    get_or_404,
    now_utc,
    require_reason,
    require_user,
    today_ba,
    version_moment,
)


def _unique_code(db: Session, model, code: str, label: str, ignore_id: int | None = None) -> str:
    cleaned = code.strip()
    if not cleaned:
        raise AppError(422, f"El código de {label} es obligatorio.")
    stmt = select(model).where(func.lower(model.code) == cleaned.lower())
    if ignore_id is not None:
        stmt = stmt.where(model.id != ignore_id)
    if db.scalar(stmt) is not None:
        raise AppError(409, f"Ya existe {label} con el código {cleaned}.")
    return cleaned


def create_unit(db: Session, code: str, name: str, decimal_places: int, user: User) -> UnitOfMeasure:
    require_user(user)
    if decimal_places < 0 or decimal_places > 4:
        raise AppError(422, "Los decimales de la unidad tienen que estar entre 0 y 4.")
    unit = UnitOfMeasure(code=_unique_code(db, UnitOfMeasure, code, "una unidad"), name=name.strip(), decimal_places=decimal_places)
    if not unit.name:
        raise AppError(422, "El nombre de la unidad es obligatorio.")
    db.add(unit)
    db.flush()
    audit(db, user, "CREAR_UNIDAD", "unit", unit.id, None, {"code": unit.code, "name": unit.name})
    return unit


def update_unit(db: Session, unit: UnitOfMeasure, name: str | None, decimal_places: int | None, user: User) -> UnitOfMeasure:
    require_user(user)
    if name is not None:
        if not name.strip():
            raise AppError(422, "El nombre de la unidad es obligatorio.")
        unit.name = name.strip()
    if decimal_places is not None:
        if decimal_places < 0 or decimal_places > 4:
            raise AppError(422, "Los decimales de la unidad tienen que estar entre 0 y 4.")
        unit.decimal_places = decimal_places
    db.flush()
    return unit


def create_work(db: Session, user: User, name: str, code: str, address: str | None, status: str, start_date: date | None, notes: str | None) -> Work:
    require_user(user)
    if not name.strip():
        raise AppError(422, "El nombre de la obra es obligatorio.")
    work = Work(
        name=name.strip(),
        code=_unique_code(db, Work, code, "una obra"),
        address=(address or "").strip() or None,
        status=status,
        start_date=start_date,
        notes=(notes or "").strip() or None,
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(work)
    db.flush()
    location_code = work.code
    if db.scalar(select(Location).where(func.lower(Location.code) == location_code.lower())) is not None:
        location_code = f"{work.code}-OBRA"
    db.add(
        Location(
            name=work.name,
            code=location_code,
            location_type=LocationType.OBRA.value,
            work_id=work.id,
            is_active=True,
            created_at=now_utc(),
        )
    )
    db.flush()
    audit(db, user, "CREAR_OBRA", "work", work.id, None, {"code": work.code, "name": work.name, "status": work.status})
    return work


def update_work(db: Session, work: Work, user: User, data: dict) -> Work:
    require_user(user)
    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise AppError(422, "El nombre de la obra es obligatorio.")
        work.name = str(data["name"]).strip()
    if "code" in data and data["code"] is not None:
        work.code = _unique_code(db, Work, data["code"], "una obra", ignore_id=work.id)
    if "address" in data:
        work.address = (data["address"] or "").strip() or None
    if "status" in data and data["status"] is not None:
        work.status = data["status"]
    if "start_date" in data:
        work.start_date = data["start_date"]
    if "notes" in data:
        work.notes = (data["notes"] or "").strip() or None
    db.flush()
    return work


def create_location(db: Session, user: User, name: str, code: str, location_type: str, work_id: int | None) -> Location:
    require_user(user)
    if not name.strip():
        raise AppError(422, "El nombre de la ubicación es obligatorio.")
    if work_id is not None:
        get_or_404(db, Work, work_id, "la obra")
    if location_type == LocationType.OBRA.value and work_id is None:
        raise AppError(422, "Una ubicación de obra tiene que estar vinculada a una obra.")
    location = Location(
        name=name.strip(),
        code=_unique_code(db, Location, code, "una ubicación"),
        location_type=location_type,
        work_id=work_id,
        is_active=True,
        created_at=now_utc(),
    )
    db.add(location)
    db.flush()
    audit(db, user, "CREAR_UBICACION", "location", location.id, None, {"code": location.code, "name": location.name})
    return location


def update_location(db: Session, location: Location, user: User, data: dict) -> Location:
    require_user(user)
    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise AppError(422, "El nombre de la ubicación es obligatorio.")
        location.name = str(data["name"]).strip()
    if "code" in data and data["code"] is not None:
        location.code = _unique_code(db, Location, data["code"], "una ubicación", ignore_id=location.id)
    if "location_type" in data and data["location_type"] is not None:
        location.location_type = data["location_type"]
    if "work_id" in data:
        if data["work_id"] is not None:
            get_or_404(db, Work, data["work_id"], "la obra")
        location.work_id = data["work_id"]
    if "is_active" in data and data["is_active"] is not None:
        location.is_active = data["is_active"]
    if location.location_type == LocationType.OBRA.value and location.work_id is None:
        raise AppError(422, "Una ubicación de obra tiene que estar vinculada a una obra.")
    db.flush()
    return location


def create_rubric(db: Session, user: User, name: str, code: str, description: str | None) -> Rubric:
    require_user(user)
    if not name.strip():
        raise AppError(422, "El nombre del rubro es obligatorio.")
    rubric = Rubric(
        name=name.strip(),
        code=_unique_code(db, Rubric, code, "un rubro"),
        description=(description or "").strip() or None,
        is_active=True,
        created_at=now_utc(),
    )
    db.add(rubric)
    db.flush()
    audit(db, user, "CREAR_RUBRO", "rubric", rubric.id, None, {"code": rubric.code, "name": rubric.name})
    return rubric


def update_rubric(db: Session, rubric: Rubric, user: User, data: dict) -> Rubric:
    require_user(user)
    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise AppError(422, "El nombre del rubro es obligatorio.")
        rubric.name = str(data["name"]).strip()
    if "code" in data and data["code"] is not None:
        rubric.code = _unique_code(db, Rubric, data["code"], "un rubro", ignore_id=rubric.id)
    if "description" in data:
        rubric.description = (data["description"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        rubric.is_active = data["is_active"]
    db.flush()
    return rubric


def create_material(db: Session, user: User, name: str, code: str, unit_id: int, category: str | None, description: str | None, notes: str | None, reorder_point: Decimal | None) -> Material:
    require_user(user)
    if not name.strip():
        raise AppError(422, "El nombre del material es obligatorio.")
    unit = get_or_404(db, UnitOfMeasure, unit_id, "la unidad")
    point = None
    if reorder_point is not None:
        point = as_qty(reorder_point)
        assert_non_negative(point, "El umbral de stock")
        assert_precision(point, unit.decimal_places, "El umbral")
    material = Material(
        name=name.strip(),
        code=_unique_code(db, Material, code, "un material"),
        unit_id=unit.id,
        category=(category or "").strip() or None,
        description=(description or "").strip() or None,
        notes=(notes or "").strip() or None,
        reorder_point=point,
        is_active=True,
        created_at=now_utc(),
    )
    db.add(material)
    db.flush()
    audit(db, user, "CREAR_MATERIAL", "material", material.id, None, {"code": material.code, "name": material.name})
    return material


def update_material(db: Session, material: Material, user: User, data: dict) -> Material:
    require_user(user)
    before = {"name": material.name, "unit_id": material.unit_id, "reorder_point": str(material.reorder_point), "is_active": material.is_active}
    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise AppError(422, "El nombre del material es obligatorio.")
        material.name = str(data["name"]).strip()
    if "code" in data and data["code"] is not None:
        material.code = _unique_code(db, Material, data["code"], "un material", ignore_id=material.id)
    if "unit_id" in data and data["unit_id"] is not None and data["unit_id"] != material.unit_id:
        from app.models.entities import InventoryMovement

        used = db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.material_id == material.id))
        if used:
            raise AppError(422, "No se puede cambiar la unidad de un material que ya tiene movimientos.")
        get_or_404(db, UnitOfMeasure, data["unit_id"], "la unidad")
        material.unit_id = data["unit_id"]
    if "category" in data:
        material.category = (data["category"] or "").strip() or None
    if "description" in data:
        material.description = (data["description"] or "").strip() or None
    if "notes" in data:
        material.notes = (data["notes"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        material.is_active = data["is_active"]
    if "reorder_point" in data:
        if data["reorder_point"] is None:
            material.reorder_point = None
        else:
            unit = db.get(UnitOfMeasure, material.unit_id)
            point = as_qty(data["reorder_point"])
            assert_non_negative(point, "El umbral de stock")
            assert_precision(point, unit.decimal_places if unit else 4, "El umbral")
            material.reorder_point = point
    db.flush()
    audit(
        db,
        user,
        "EDITAR_MATERIAL",
        "material",
        material.id,
        before,
        {"name": material.name, "unit_id": material.unit_id, "reorder_point": str(material.reorder_point), "is_active": material.is_active},
    )
    return material


def create_conversion(db: Session, user: User, material_id: int, from_unit_id: int, to_unit_id: int, factor: Decimal, notes: str | None) -> MaterialUnitConversion:
    require_user(user)
    material = get_or_404(db, Material, material_id, "el material")
    if from_unit_id == to_unit_id:
        raise AppError(422, "La conversión tiene que ser entre unidades distintas.")
    get_or_404(db, UnitOfMeasure, from_unit_id, "la unidad de origen")
    to_unit = get_or_404(db, UnitOfMeasure, to_unit_id, "la unidad de destino")
    if to_unit.id != material.unit_id:
        raise AppError(422, "La conversión de esta versión tiene que llegar a la unidad de inventario del material.")
    qty = as_qty(factor)
    assert_positive(qty, "El factor de conversión")
    existing = db.scalar(
        select(MaterialUnitConversion).where(
            MaterialUnitConversion.material_id == material.id,
            MaterialUnitConversion.from_unit_id == from_unit_id,
            MaterialUnitConversion.to_unit_id == to_unit.id,
        )
    )
    if existing is not None:
        raise AppError(409, "Esa conversión ya está configurada para el material.")
    row = MaterialUnitConversion(
        material_id=material.id,
        from_unit_id=from_unit_id,
        to_unit_id=to_unit.id,
        factor=qty,
        notes=(notes or "").strip() or None,
    )
    db.add(row)
    db.flush()
    audit(db, user, "CREAR_CONVERSION", "material_unit_conversion", row.id, None, {"material_id": material.id, "factor": str(qty)})
    return row


def conversion_factor(db: Session, material: Material, output_unit_id: int) -> Decimal:
    if output_unit_id == material.unit_id:
        return Decimal("1.0000")
    row = db.scalar(
        select(MaterialUnitConversion).where(
            MaterialUnitConversion.material_id == material.id,
            MaterialUnitConversion.from_unit_id == output_unit_id,
            MaterialUnitConversion.to_unit_id == material.unit_id,
        )
    )
    if row is None:
        raise AppError(422, "No hay una conversión explícita entre la unidad indicada y la unidad de inventario del material.")
    return as_qty(row.factor)


def create_task(db: Session, user: User, work_id: int, rubric_id: int, name: str, description: str | None, unit_id: int, planned_qty: Decimal | None, execution_start: date | None, execution_end: date | None, status: str, notes: str | None) -> Task:
    require_user(user)
    work = get_or_404(db, Work, work_id, "la obra")
    rubric = get_or_404(db, Rubric, rubric_id, "el rubro")
    ensure_active(rubric, "El rubro")
    unit = get_or_404(db, UnitOfMeasure, unit_id, "la unidad")
    if not name.strip():
        raise AppError(422, "El nombre de la tarea es obligatorio.")
    planned = None
    if planned_qty is not None:
        planned = as_qty(planned_qty)
        assert_non_negative(planned, "La cantidad planificada")
        assert_precision(planned, unit.decimal_places, "La cantidad planificada")
    if execution_start and execution_end and execution_start > execution_end:
        raise AppError(422, "El período de la tarea tiene la fecha inicial después de la final.")
    task = Task(
        work_id=work.id,
        rubric_id=rubric.id,
        name=name.strip(),
        description=(description or "").strip() or None,
        unit_id=unit.id,
        planned_qty=planned,
        execution_start=execution_start,
        execution_end=execution_end,
        status=status,
        notes=(notes or "").strip() or None,
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(task)
    db.flush()
    audit(db, user, "CREAR_TAREA", "task", task.id, None, {"name": task.name, "work_id": work.id, "rubric_id": rubric.id})
    return task


def update_task(db: Session, task: Task, user: User, data: dict) -> Task:
    require_user(user)
    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise AppError(422, "El nombre de la tarea es obligatorio.")
        task.name = str(data["name"]).strip()
    if "description" in data:
        task.description = (data["description"] or "").strip() or None
    if "rubric_id" in data and data["rubric_id"] is not None:
        rubric = get_or_404(db, Rubric, data["rubric_id"], "el rubro")
        ensure_active(rubric, "El rubro")
        task.rubric_id = rubric.id
    if "unit_id" in data and data["unit_id"] is not None and data["unit_id"] != task.unit_id:
        used = db.scalar(select(func.count()).select_from(TaskExecution).where(TaskExecution.task_id == task.id))
        rules = db.scalar(select(func.count()).select_from(ConsumptionRule).where(ConsumptionRule.task_id == task.id))
        if used or rules:
            raise AppError(422, "No se puede cambiar la unidad de una tarea que ya tiene avances o reglas.")
        get_or_404(db, UnitOfMeasure, data["unit_id"], "la unidad")
        task.unit_id = data["unit_id"]
    if "planned_qty" in data:
        if data["planned_qty"] is None:
            task.planned_qty = None
        else:
            unit = db.get(UnitOfMeasure, task.unit_id)
            planned = as_qty(data["planned_qty"])
            assert_non_negative(planned, "La cantidad planificada")
            assert_precision(planned, unit.decimal_places if unit else 4, "La cantidad planificada")
            task.planned_qty = planned
    if "execution_start" in data:
        task.execution_start = data["execution_start"]
    if "execution_end" in data:
        task.execution_end = data["execution_end"]
    if task.execution_start and task.execution_end and task.execution_start > task.execution_end:
        raise AppError(422, "El período de la tarea tiene la fecha inicial después de la final.")
    if "status" in data and data["status"] is not None:
        task.status = data["status"]
    if "notes" in data:
        task.notes = (data["notes"] or "").strip() or None
    db.flush()
    return task


def executed_qty(db: Session, task_id: int, date_from: date | None = None, date_to: date | None = None) -> Decimal:
    stmt = select(func.coalesce(func.sum(TaskExecution.quantity_delta), 0)).where(
        TaskExecution.task_id == task_id,
        TaskExecution.status == RecordStatus.CONFIRMADO.value,
    )
    if date_from is not None:
        stmt = stmt.where(TaskExecution.execution_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(TaskExecution.execution_date <= date_to)
    return as_qty(db.scalar(stmt) or 0)


def _line_snapshot(line: TheoreticalConsumptionLine) -> dict:
    return {
        "material_id": line.material_id,
        "rule_version_id": line.rule_version_id,
        "coefficient": str(line.coefficient_snapshot),
        "method": line.method_snapshot,
        "input_qty": str(line.input_qty),
        "output_qty": str(line.output_qty),
        "factor": str(line.conversion_factor_snapshot),
    }


def active_versions(db: Session, task_id: int, execution_date: date) -> list[ConsumptionRuleVersion]:
    moment = version_moment(execution_date)
    rows = db.scalars(
        select(ConsumptionRuleVersion)
        .join(ConsumptionRule, ConsumptionRule.id == ConsumptionRuleVersion.rule_id)
        .where(
            ConsumptionRule.task_id == task_id,
            ConsumptionRule.is_active.is_(True),
            ConsumptionRuleVersion.valid_from <= moment,
            or_(ConsumptionRuleVersion.valid_to.is_(None), ConsumptionRuleVersion.valid_to > moment),
        )
    ).all()
    chosen: dict[int, ConsumptionRuleVersion] = {}
    for row in rows:
        current = chosen.get(row.rule_id)
        if current is None or row.version > current.version:
            chosen[row.rule_id] = row
    return list(chosen.values())


def _add_line_from_version(db: Session, execution: TaskExecution, version: ConsumptionRuleVersion, quantity_delta: Decimal) -> None:
    material = db.get(Material, version.rule.material_id)
    factor = conversion_factor(db, material, version.output_unit_id)
    output = coefficient_output(quantity_delta, version.coefficient, factor)
    db.add(
        TheoreticalConsumptionLine(
            task_execution_id=execution.id,
            material_id=material.id,
            rule_version_id=version.id,
            coefficient_snapshot=as_qty(version.coefficient),
            method_snapshot=version.method,
            input_qty=quantity_delta,
            output_qty=output,
            output_unit_id=material.unit_id,
            conversion_factor_snapshot=factor,
        )
    )


def _add_line_from_original(db: Session, execution: TaskExecution, source: TheoreticalConsumptionLine, quantity_delta: Decimal) -> None:
    output = coefficient_output(quantity_delta, source.coefficient_snapshot, source.conversion_factor_snapshot)
    db.add(
        TheoreticalConsumptionLine(
            task_execution_id=execution.id,
            material_id=source.material_id,
            rule_version_id=source.rule_version_id,
            coefficient_snapshot=source.coefficient_snapshot,
            method_snapshot=source.method_snapshot,
            input_qty=quantity_delta,
            output_qty=output,
            output_unit_id=source.output_unit_id,
            conversion_factor_snapshot=source.conversion_factor_snapshot,
        )
    )


def record_execution(
    db: Session,
    user: User,
    task: Task,
    quantity_delta: Decimal | None,
    new_total: Decimal | None,
    execution_date: date | None,
    notes: str | None,
    corrects_execution_id: int | None = None,
) -> TaskExecution:
    require_user(user)
    if quantity_delta is not None and new_total is not None:
        raise AppError(422, "Indicá la cantidad de este avance o el nuevo total acumulado.")
    current = executed_qty(db, task.id)
    unit = db.get(UnitOfMeasure, task.unit_id)
    if new_total is not None:
        total = as_qty(new_total)
        assert_precision(total, unit.decimal_places if unit else 4, "La cantidad ejecutada")
        quantity_delta = as_qty(total - current)
    if quantity_delta is None:
        raise AppError(422, "Indicá la cantidad ejecutada.")
    quantity_delta = as_qty(quantity_delta)
    assert_precision(abs(quantity_delta), unit.decimal_places if unit else 4, "La cantidad ejecutada")
    if quantity_delta == 0:
        raise AppError(422, "La cantidad ejecutada no cambia. No se registró un avance nuevo.")
    if current + quantity_delta < 0:
        raise AppError(422, "La cantidad ejecutada acumulada no puede quedar por debajo de cero.")
    when = execution_date or today_ba()
    original = None
    if corrects_execution_id is not None:
        original = get_or_404(db, TaskExecution, corrects_execution_id, "el avance")
        if original.task_id != task.id:
            raise AppError(422, "La corrección tiene que referirse a un avance de la misma tarea.")
        if original.status != RecordStatus.CONFIRMADO.value:
            raise AppError(422, "El avance original no está confirmado.")
        if quantity_delta == 0:
            raise AppError(422, "La corrección tiene que modificar la cantidad.")
    execution = TaskExecution(
        task_id=task.id,
        quantity_delta=quantity_delta,
        execution_date=when,
        notes=(notes or "").strip() or None,
        recorded_by_user_id=user.id,
        corrects_execution_id=original.id if original else None,
        status=RecordStatus.CONFIRMADO.value,
        created_at=now_utc(),
    )
    db.add(execution)
    db.flush()
    if original is not None:
        for line in original.lines:
            _add_line_from_original(db, execution, line, quantity_delta)
    else:
        for version in active_versions(db, task.id, when):
            _add_line_from_version(db, execution, version, quantity_delta)
    db.flush()
    audit(
        db,
        user,
        "REGISTRAR_AVANCE",
        "task_execution",
        execution.id,
        None,
        {"task_id": task.id, "quantity_delta": str(quantity_delta), "execution_date": str(when), "corrects": corrects_execution_id},
    )
    return execution


def edit_execution(db: Session, execution: TaskExecution, user: User, new_delta: Decimal, reason: str) -> TaskExecution:
    require_user(user)
    reason = require_reason(reason)
    if execution.status != RecordStatus.CONFIRMADO.value:
        raise AppError(422, "El avance no está confirmado.")
    task = db.get(Task, execution.task_id)
    unit = db.get(UnitOfMeasure, task.unit_id)
    new_delta = as_qty(new_delta)
    assert_precision(abs(new_delta), unit.decimal_places if unit else 4, "La cantidad ejecutada")
    if new_delta == 0:
        raise AppError(422, "Un avance confirmado no puede quedar en cero. Anulalo si corresponde.")
    others = as_qty(executed_qty(db, task.id) - execution.quantity_delta)
    if others + new_delta < 0:
        raise AppError(422, "La cantidad ejecutada acumulada no puede quedar por debajo de cero.")
    before = {"quantity_delta": str(execution.quantity_delta), "lines": [_line_snapshot(line) for line in execution.lines]}
    execution.quantity_delta = new_delta
    for line in execution.lines:
        line.input_qty = new_delta
        line.output_qty = coefficient_output(new_delta, line.coefficient_snapshot, line.conversion_factor_snapshot)
    db.flush()
    audit(db, user, "CORREGIR_AVANCE", "task_execution", execution.id, before, {"quantity_delta": str(new_delta), "lines": [_line_snapshot(line) for line in execution.lines]}, reason)
    return execution


def void_execution(db: Session, execution: TaskExecution, user: User, reason: str) -> TaskExecution:
    require_user(user)
    reason = require_reason(reason)
    if execution.status == RecordStatus.ANULADO.value:
        raise AppError(422, "El avance ya está anulado.")
    before = {"status": execution.status, "quantity_delta": str(execution.quantity_delta), "lines": [_line_snapshot(line) for line in execution.lines]}
    execution.status = RecordStatus.ANULADO.value
    execution.voided_by_user_id = user.id
    execution.voided_at = now_utc()
    execution.void_reason = reason
    db.flush()
    audit(db, user, "ANULAR_AVANCE", "task_execution", execution.id, before, {"status": execution.status}, reason)
    return execution


def create_rule(
    db: Session,
    user: User,
    task: Task,
    material_id: int,
    coefficient: Decimal,
    output_unit_id: int | None,
    reason: str | None,
    reference_unit_id: int | None = None,
) -> ConsumptionRule:
    require_user(user)
    material = get_or_404(db, Material, material_id, "el material")
    ensure_active(material, "El material")
    existing = db.scalar(select(ConsumptionRule).where(ConsumptionRule.task_id == task.id, ConsumptionRule.material_id == material.id))
    if existing is not None:
        raise AppError(409, "Esa tarea ya tiene una regla para este material. Registrá una nueva versión.")
    if reference_unit_id is not None and reference_unit_id != task.unit_id:
        raise AppError(422, "La unidad de referencia de la regla tiene que coincidir con la unidad de la tarea.")
    output_unit = output_unit_id or material.unit_id
    get_or_404(db, UnitOfMeasure, output_unit, "la unidad de salida")
    factor = conversion_factor(db, material, output_unit)
    coeff = as_qty(coefficient)
    assert_positive(coeff, "El coeficiente")
    if CalcMethod.COEFFICIENT_PER_EXECUTED.value != "COEFICIENTE_POR_EJECUTADO":
        raise AppError(500, "El método de cálculo no está disponible.")
    rule = ConsumptionRule(task_id=task.id, material_id=material.id, is_active=True, created_at=now_utc())
    db.add(rule)
    db.flush()
    version = ConsumptionRuleVersion(
        rule_id=rule.id,
        version=1,
        method=CalcMethod.COEFFICIENT_PER_EXECUTED.value,
        coefficient=coeff,
        reference_unit_id=task.unit_id,
        output_unit_id=output_unit,
        valid_from=now_utc(),
        valid_to=None,
        created_by_user_id=user.id,
        change_reason=(reason or "").strip() or None,
    )
    db.add(version)
    db.flush()
    audit(db, user, "CREAR_REGLA", "consumption_rule", rule.id, None, {"task_id": task.id, "material_id": material.id, "coefficient": str(coeff), "factor": str(factor)})
    return rule


def new_rule_version(
    db: Session,
    user: User,
    rule: ConsumptionRule,
    coefficient: Decimal,
    output_unit_id: int | None,
    reason: str,
    reference_unit_id: int | None = None,
) -> ConsumptionRuleVersion:
    require_user(user)
    reason = require_reason(reason)
    task = db.get(Task, rule.task_id)
    material = db.get(Material, rule.material_id)
    if reference_unit_id is not None and reference_unit_id != task.unit_id:
        raise AppError(422, "La unidad de referencia de la regla tiene que coincidir con la unidad de la tarea.")
    current = db.scalar(
        select(ConsumptionRuleVersion)
        .where(ConsumptionRuleVersion.rule_id == rule.id, ConsumptionRuleVersion.valid_to.is_(None))
        .order_by(ConsumptionRuleVersion.version.desc())
    )
    if current is None:
        raise AppError(422, "La regla no tiene una versión vigente.")
    output_unit = output_unit_id or current.output_unit_id
    conversion_factor(db, material, output_unit)
    coeff = as_qty(coefficient)
    assert_positive(coeff, "El coeficiente")
    moment = now_utc()
    before = {"version": current.version, "coefficient": str(current.coefficient), "output_unit_id": current.output_unit_id}
    current.valid_to = moment
    version = ConsumptionRuleVersion(
        rule_id=rule.id,
        version=current.version + 1,
        method=CalcMethod.COEFFICIENT_PER_EXECUTED.value,
        coefficient=coeff,
        reference_unit_id=task.unit_id,
        output_unit_id=output_unit,
        valid_from=moment,
        valid_to=None,
        created_by_user_id=user.id,
        change_reason=reason,
    )
    db.add(version)
    rule.is_active = True
    db.flush()
    audit(db, user, "NUEVA_VERSION_REGLA", "consumption_rule", rule.id, before, {"version": version.version, "coefficient": str(coeff)}, reason)
    return version


def deactivate_rule(db: Session, user: User, rule: ConsumptionRule, reason: str) -> ConsumptionRule:
    require_user(user)
    reason = require_reason(reason)
    current = db.scalar(
        select(ConsumptionRuleVersion).where(ConsumptionRuleVersion.rule_id == rule.id, ConsumptionRuleVersion.valid_to.is_(None))
    )
    if current is not None:
        current.valid_to = now_utc()
    rule.is_active = False
    db.flush()
    audit(db, user, "DESACTIVAR_REGLA", "consumption_rule", rule.id, {"is_active": True}, {"is_active": False}, reason)
    return rule


def current_version(db: Session, rule: ConsumptionRule) -> ConsumptionRuleVersion | None:
    return db.scalar(
        select(ConsumptionRuleVersion)
        .where(ConsumptionRuleVersion.rule_id == rule.id, ConsumptionRuleVersion.valid_to.is_(None))
        .order_by(ConsumptionRuleVersion.version.desc())
    )


def projected_theoretical(db: Session, task: Task) -> list[dict]:
    if task.planned_qty is None:
        return []
    rows = []
    for version in active_versions(db, task.id, today_ba()):
        material = db.get(Material, version.rule.material_id)
        factor = conversion_factor(db, material, version.output_unit_id)
        output = coefficient_output(task.planned_qty, version.coefficient, factor)
        rows.append(
            {
                "material_id": material.id,
                "material_name": material.name,
                "material_code": material.code,
                "coefficient": version.coefficient,
                "quantity": output,
                "unit_code": material.unit.code,
                "label": "Proyección con la regla vigente. No forma parte del historial.",
            }
        )
    return rows
