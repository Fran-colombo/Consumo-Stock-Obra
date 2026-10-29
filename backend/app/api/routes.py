from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.presenters import (
    adjustment_out,
    consumption_out,
    conversion_out,
    execution_out,
    location_out,
    material_out,
    movement_out,
    order_out,
    page,
    paginate,
    receipt_out,
    rubric_out,
    rule_out,
    supplier_out,
    task_out,
    transfer_out,
    unit_out,
    user_out,
    work_out,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_sysadmin
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.entities import (
    AuditLog,
    ConsumptionRule,
    GoodsReceipt,
    GoodsReceiptItem,
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
from app.models.enums import UserRole
from app.schemas import (
    AdjustmentEdit,
    AdjustmentIn,
    ConsumptionCorrectionIn,
    ConsumptionEdit,
    ConsumptionIn,
    ConversionIn,
    DispatchIn,
    ExecutionEdit,
    ExecutionIn,
    LocationIn,
    LocationUpdate,
    LoginIn,
    MaterialIn,
    MaterialUpdate,
    OrderIn,
    OrderItemQty,
    OrderUpdate,
    ReasonIn,
    ReceiptCorrectionIn,
    ReceiptIn,
    ReceiptItemEdit,
    ReceiveTransferIn,
    ResolveDiscrepancyIn,
    RubricIn,
    RubricUpdate,
    RuleIn,
    RuleVersionIn,
    SettingsUpdate,
    SupplierIn,
    SupplierUpdate,
    TaskIn,
    TaskUpdate,
    TransferIn,
    UnitIn,
    UnitUpdate,
    UserIn,
    UserUpdate,
    WorkIn,
    WorkUpdate,
)
from app.services.adjustments import edit_adjustment, register_adjustment, void_adjustment
from app.services.common import begin_idempotency, finish_idempotency, get_or_404, set_setting, setting_bool
from app.services.consumption import correct_consumption, edit_consumption, register_consumption, void_consumption
from app.services.insights import (
    comparison_rows,
    dashboard,
    investigation,
    movements_query,
    purchase_report_rows,
    rows_to_csv,
    rows_to_xlsx,
    stock_rows,
    task_theoretical_view,
)
from app.services.planning import (
    create_location,
    create_material,
    create_conversion,
    create_rubric,
    create_rule,
    create_task,
    create_unit,
    create_work,
    deactivate_rule,
    edit_execution,
    new_rule_version,
    record_execution,
    update_location,
    update_material,
    update_rubric,
    update_task,
    update_unit,
    update_work,
    void_execution,
)
from app.services.purchasing import (
    cancel_purchase_order,
    change_ordered_qty,
    confirm_purchase_order,
    correct_receipt,
    create_purchase_order,
    create_supplier,
    edit_receipt_item,
    register_receipt,
    update_purchase_order,
    update_supplier,
    void_receipt,
)
from app.services.stock import consistency_report, get_on_hand
from app.services.transfers import (
    cancel_transfer,
    create_transfer,
    dispatch_transfer,
    receive_transfer,
    resolve_discrepancy,
    void_transfer,
)

router = APIRouter()


def _replay(db: Session, user: User, key: str | None, path: str, payload: dict):
    return begin_idempotency(db, user, key, path, payload)


def _finish(db: Session, user: User, key: str, status: int, body: dict) -> JSONResponse:
    finish_idempotency(db, user, key, status, body)
    return JSONResponse(status_code=status, content=body)


def _search(model, column, q: str | None):
    return func.lower(column).contains(q.strip().lower()) if q and q.strip() else None


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise AppError(401, "Usuario o contraseña incorrectos.")
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer", "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(User).order_by(User.full_name)).all()
    return [user_out(row) for row in rows]


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), actor: User = Depends(require_sysadmin)):
    role = body.role.strip().upper()
    if role not in (UserRole.SYSADMIN.value, UserRole.OPERADOR.value):
        raise AppError(422, "El rol tiene que ser SYSADMIN u OPERADOR.")
    username = body.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise AppError(409, "Ese nombre de usuario ya existe.")
    user = User(
        username=username,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role=role,
        is_active=True,
        created_at=__import__("app.services.common", fromlist=["now_utc"]).now_utc(),
    )
    db.add(user)
    db.flush()
    from app.services.common import audit

    audit(db, actor, "CREAR_USUARIO", "user", user.id, None, {"username": user.username, "role": user.role})
    return user_out(user)


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), actor: User = Depends(require_sysadmin)):
    user = get_or_404(db, User, user_id, "el usuario")
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"] is not None:
        user.full_name = data["full_name"].strip()
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])
    if "role" in data and data["role"] is not None:
        role = data["role"].strip().upper()
        if role not in (UserRole.SYSADMIN.value, UserRole.OPERADOR.value):
            raise AppError(422, "El rol tiene que ser SYSADMIN u OPERADOR.")
        user.role = role
    if "is_active" in data and data["is_active"] is not None:
        if user.id == actor.id and data["is_active"] is False:
            raise AppError(422, "No podés desactivar tu propio usuario.")
        user.is_active = data["is_active"]
    db.flush()
    return user_out(user)


@router.get("/settings")
def get_settings_route(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {
        "allow_negative_stock": setting_bool(db, "allow_negative_stock"),
        "allow_over_receipt": setting_bool(db, "allow_over_receipt"),
    }


@router.put("/settings")
def put_settings(body: SettingsUpdate, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    from app.services.common import audit

    before = get_settings_route(db, user)
    data = body.model_dump(exclude_unset=True)
    if "allow_negative_stock" in data:
        set_setting(db, "allow_negative_stock", "true" if data["allow_negative_stock"] else "false")
    if "allow_over_receipt" in data:
        set_setting(db, "allow_over_receipt", "true" if data["allow_over_receipt"] else "false")
    after = {
        "allow_negative_stock": setting_bool(db, "allow_negative_stock"),
        "allow_over_receipt": setting_bool(db, "allow_over_receipt"),
    }
    audit(db, user, "CAMBIAR_CONFIGURACION", "settings", 0, before, after)
    return after


@router.get("/units")
def list_units(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [unit_out(row) for row in db.scalars(select(UnitOfMeasure).order_by(UnitOfMeasure.name)).all()]


@router.post("/units", status_code=201)
def post_unit(body: UnitIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return unit_out(create_unit(db, body.code, body.name, body.decimal_places, user))


@router.patch("/units/{unit_id}")
def patch_unit(unit_id: int, body: UnitUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    unit = get_or_404(db, UnitOfMeasure, unit_id, "la unidad")
    data = body.model_dump(exclude_unset=True)
    return unit_out(update_unit(db, unit, data.get("name"), data.get("decimal_places"), user))


@router.get("/works")
def list_works(
    q: str | None = None,
    status: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Work).order_by(Work.name)
    if status:
        stmt = stmt.where(Work.status == status)
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Work.name).like(needle), func.lower(Work.code).like(needle)))
    rows = [work_out(db, row) for row in db.scalars(stmt).all()]
    return paginate(rows, page_number, page_size)


@router.post("/works", status_code=201)
def post_work(body: WorkIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    work = create_work(db, user, body.name, body.code, body.address, body.status, body.start_date, body.notes)
    return work_out(db, work)


@router.get("/works/{work_id}")
def get_work(work_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return work_out(db, get_or_404(db, Work, work_id, "la obra"))


@router.patch("/works/{work_id}")
def patch_work(work_id: int, body: WorkUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    work = get_or_404(db, Work, work_id, "la obra")
    return work_out(db, update_work(db, work, user, body.model_dump(exclude_unset=True)))


@router.get("/locations")
def list_locations(work_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(Location).order_by(Location.name)
    if work_id is not None:
        stmt = stmt.where(Location.work_id == work_id)
    return [location_out(db, row) for row in db.scalars(stmt).all()]


@router.post("/locations", status_code=201)
def post_location(body: LocationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return location_out(db, create_location(db, user, body.name, body.code, body.location_type, body.work_id))


@router.patch("/locations/{location_id}")
def patch_location(location_id: int, body: LocationUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    location = get_or_404(db, Location, location_id, "la ubicación")
    return location_out(db, update_location(db, location, user, body.model_dump(exclude_unset=True)))


@router.get("/rubrics")
def list_rubrics(q: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(Rubric).order_by(Rubric.name)
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Rubric.name).like(needle), func.lower(Rubric.code).like(needle)))
    return [rubric_out(row) for row in db.scalars(stmt).all()]


@router.post("/rubrics", status_code=201)
def post_rubric(body: RubricIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return rubric_out(create_rubric(db, user, body.name, body.code, body.description))


@router.patch("/rubrics/{rubric_id}")
def patch_rubric(rubric_id: int, body: RubricUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rubric = get_or_404(db, Rubric, rubric_id, "el rubro")
    return rubric_out(update_rubric(db, rubric, user, body.model_dump(exclude_unset=True)))


@router.get("/materials")
def list_materials(
    q: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Material).order_by(Material.name)
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Material.name).like(needle), func.lower(Material.code).like(needle), func.lower(Material.category).like(needle)))
    rows = [material_out(db, row) for row in db.scalars(stmt).all()]
    return paginate(rows, page_number, page_size)


@router.post("/materials", status_code=201)
def post_material(body: MaterialIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    material = create_material(db, user, body.name, body.code, body.unit_id, body.category, body.description, body.notes, body.reorder_point)
    return material_out(db, material)


@router.patch("/materials/{material_id}")
def patch_material(material_id: int, body: MaterialUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    material = get_or_404(db, Material, material_id, "el material")
    return material_out(db, update_material(db, material, user, body.model_dump(exclude_unset=True)))


@router.get("/conversions")
def list_conversions(material_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(MaterialUnitConversion)
    if material_id is not None:
        stmt = stmt.where(MaterialUnitConversion.material_id == material_id)
    return [conversion_out(row) for row in db.scalars(stmt).all()]


@router.post("/conversions", status_code=201)
def post_conversion(body: ConversionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = create_conversion(db, user, body.material_id, body.from_unit_id, body.to_unit_id, body.factor, body.notes)
    return conversion_out(row)


@router.get("/tasks")
def list_tasks(
    work_id: int | None = None,
    rubric_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Task).order_by(Task.name)
    if work_id is not None:
        stmt = stmt.where(Task.work_id == work_id)
    if rubric_id is not None:
        stmt = stmt.where(Task.rubric_id == rubric_id)
    return [task_out(db, row) for row in db.scalars(stmt).all()]


@router.post("/tasks", status_code=201)
def post_task(body: TaskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = create_task(
        db,
        user,
        body.work_id,
        body.rubric_id,
        body.name,
        body.description,
        body.unit_id,
        body.planned_qty,
        body.execution_start,
        body.execution_end,
        body.status,
        body.notes,
    )
    return task_out(db, task)


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return task_out(db, get_or_404(db, Task, task_id, "la tarea"))


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = get_or_404(db, Task, task_id, "la tarea")
    return task_out(db, update_task(db, task, user, body.model_dump(exclude_unset=True)))


@router.get("/tasks/{task_id}/theoretical")
def get_theoretical(task_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    task = get_or_404(db, Task, task_id, "la tarea")
    view = task_theoretical_view(db, task)
    from app.api.presenters import _qty

    view["executed_qty"] = _qty(view["executed_qty"])
    view["planned_qty"] = _qty(view["planned_qty"])
    for row in view["materials"]:
        row["theoretical_qty"] = _qty(row["theoretical_qty"])
    for row in view["projection"]:
        row["coefficient"] = _qty(row["coefficient"])
        row["quantity"] = _qty(row["quantity"])
    return view


@router.get("/tasks/{task_id}/rules")
def list_rules(task_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    get_or_404(db, Task, task_id, "la tarea")
    rows = db.scalars(select(ConsumptionRule).where(ConsumptionRule.task_id == task_id)).all()
    return [rule_out(db, row) for row in rows]


@router.post("/tasks/{task_id}/rules", status_code=201)
def post_rule(task_id: int, body: RuleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = get_or_404(db, Task, task_id, "la tarea")
    rule = create_rule(db, user, task, body.material_id, body.coefficient, body.output_unit_id, body.reason, body.reference_unit_id)
    return rule_out(db, rule)


@router.post("/rules/{rule_id}/versions", status_code=201)
def post_rule_version(rule_id: int, body: RuleVersionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = get_or_404(db, ConsumptionRule, rule_id, "la regla")
    new_rule_version(db, user, rule, body.coefficient, body.output_unit_id, body.reason, body.reference_unit_id)
    return rule_out(db, rule)


@router.post("/rules/{rule_id}/deactivate")
def post_deactivate_rule(rule_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = get_or_404(db, ConsumptionRule, rule_id, "la regla")
    return rule_out(db, deactivate_rule(db, user, rule, body.reason))


@router.get("/tasks/{task_id}/executions")
def list_executions(task_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    get_or_404(db, Task, task_id, "la tarea")
    rows = db.scalars(select(TaskExecution).where(TaskExecution.task_id == task_id).order_by(TaskExecution.execution_date, TaskExecution.id)).all()
    return [execution_out(db, row) for row in rows]


@router.post("/tasks/{task_id}/executions", status_code=201)
def post_execution(
    task_id: int,
    body: ExecutionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    task = get_or_404(db, Task, task_id, "la tarea")
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, f"/tasks/{task_id}/executions", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    execution = record_execution(db, user, task, body.quantity_delta, body.new_total, body.execution_date, body.notes, body.corrects_execution_id)
    return _finish(db, user, idempotency_key or "", 201, execution_out(db, execution))


@router.patch("/executions/{execution_id}")
def patch_execution(execution_id: int, body: ExecutionEdit, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    execution = get_or_404(db, TaskExecution, execution_id, "el avance")
    return execution_out(db, edit_execution(db, execution, user, body.quantity_delta, body.reason))


@router.post("/executions/{execution_id}/void")
def post_void_execution(execution_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    execution = get_or_404(db, TaskExecution, execution_id, "el avance")
    return execution_out(db, void_execution(db, execution, user, body.reason))


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [supplier_out(row) for row in db.scalars(select(Supplier).order_by(Supplier.name)).all()]


@router.post("/suppliers", status_code=201)
def post_supplier(body: SupplierIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return supplier_out(create_supplier(db, user, body.name, body.contact))


@router.patch("/suppliers/{supplier_id}")
def patch_supplier(supplier_id: int, body: SupplierUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    supplier = get_or_404(db, Supplier, supplier_id, "el proveedor")
    return supplier_out(update_supplier(db, supplier, body.model_dump(exclude_unset=True)))


@router.get("/purchase-orders")
def list_orders(
    work_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    if work_id is not None:
        stmt = stmt.where(PurchaseOrder.work_id == work_id)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    rows = db.scalars(stmt).all()
    if q and q.strip():
        needle = q.strip().lower()
        rows = [row for row in rows if needle in row.number.lower() or needle in row.supplier.name.lower()]
    return paginate([order_out(db, row) for row in rows], page_number, page_size)


@router.post("/purchase-orders", status_code=201)
def post_order(body: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = create_purchase_order(
        db,
        user,
        body.supplier_id,
        body.destination_location_id,
        body.work_id,
        body.expected_date,
        body.notes,
        [item.model_dump() for item in body.items],
    )
    return order_out(db, order)


@router.get("/purchase-orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return order_out(db, get_or_404(db, PurchaseOrder, order_id, "la orden"))


@router.patch("/purchase-orders/{order_id}")
def patch_order(order_id: int, body: OrderUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = get_or_404(db, PurchaseOrder, order_id, "la orden")
    data = body.model_dump(exclude_unset=True)
    if "items" in data and data["items"] is not None:
        data["items"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in body.items]
    return order_out(db, update_purchase_order(db, order, user, data))


@router.post("/purchase-orders/{order_id}/confirm")
def post_confirm_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = get_or_404(db, PurchaseOrder, order_id, "la orden")
    return order_out(db, confirm_purchase_order(db, order, user))


@router.post("/purchase-orders/{order_id}/cancel")
def post_cancel_order(order_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = get_or_404(db, PurchaseOrder, order_id, "la orden")
    return order_out(db, cancel_purchase_order(db, order, user, body.reason))


@router.patch("/purchase-order-items/{item_id}")
def patch_order_item(item_id: int, body: OrderItemQty, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_or_404(db, PurchaseOrderItem, item_id, "el ítem")
    change_ordered_qty(db, item, user, body.quantity, body.reason)
    return order_out(db, item.order)


@router.post("/purchase-orders/{order_id}/receipts", status_code=201)
def post_receipt(
    order_id: int,
    body: ReceiptIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    order = get_or_404(db, PurchaseOrder, order_id, "la orden")
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, f"/purchase-orders/{order_id}/receipts", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    receipt = register_receipt(db, user, order, body.location_id, [item.model_dump() for item in body.items], body.received_at, body.notes)
    return _finish(db, user, idempotency_key or "", 201, receipt_out(receipt))


@router.get("/purchase-orders/{order_id}/receipts")
def list_receipts(order_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    get_or_404(db, PurchaseOrder, order_id, "la orden")
    rows = db.scalars(select(GoodsReceipt).where(GoodsReceipt.purchase_order_id == order_id).order_by(GoodsReceipt.received_at)).all()
    return [receipt_out(row) for row in rows]


@router.post("/receipts/{receipt_id}/corrections", status_code=201)
def post_receipt_correction(
    receipt_id: int,
    body: ReceiptCorrectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    receipt = get_or_404(db, GoodsReceipt, receipt_id, "la recepción")
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, f"/receipts/{receipt_id}/corrections", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    created = correct_receipt(db, user, receipt, [item.model_dump() for item in body.items], body.reason, body.received_at)
    return _finish(db, user, idempotency_key or "", 201, receipt_out(created))


@router.post("/receipts/{receipt_id}/void")
def post_void_receipt(receipt_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    receipt = get_or_404(db, GoodsReceipt, receipt_id, "la recepción")
    return receipt_out(void_receipt(db, receipt, user, body.reason))


@router.patch("/receipt-items/{item_id}")
def patch_receipt_item(item_id: int, body: ReceiptItemEdit, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    item = get_or_404(db, GoodsReceiptItem, item_id, "el ítem recibido")
    edit_receipt_item(db, item, user, body.quantity, body.reason)
    return receipt_out(item.receipt)


@router.get("/consumptions")
def list_consumptions(
    work_id: int | None = None,
    task_id: int | None = None,
    material_id: int | None = None,
    page_number: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(MaterialConsumption).order_by(MaterialConsumption.consumed_at.desc())
    if work_id is not None:
        stmt = stmt.where(MaterialConsumption.work_id == work_id)
    if task_id is not None:
        stmt = stmt.where(MaterialConsumption.task_id == task_id)
    if material_id is not None:
        stmt = stmt.where(MaterialConsumption.material_id == material_id)
    rows = [consumption_out(row) for row in db.scalars(stmt).all()]
    return paginate(rows, page_number, page_size)


@router.post("/consumptions", status_code=201)
def post_consumption(
    body: ConsumptionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, "/consumptions", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    row = register_consumption(db, user, body.work_id, body.task_id, body.location_id, body.material_id, body.quantity, body.consumed_at, body.notes)
    return _finish(db, user, idempotency_key or "", 201, consumption_out(row))


@router.post("/consumptions/{consumption_id}/corrections", status_code=201)
def post_consumption_correction(
    consumption_id: int,
    body: ConsumptionCorrectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    original = get_or_404(db, MaterialConsumption, consumption_id, "el consumo")
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, f"/consumptions/{consumption_id}/corrections", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    row = correct_consumption(db, user, original, body.quantity, body.reason, body.consumed_at)
    return _finish(db, user, idempotency_key or "", 201, consumption_out(row))


@router.patch("/consumptions/{consumption_id}")
def patch_consumption(consumption_id: int, body: ConsumptionEdit, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    row = get_or_404(db, MaterialConsumption, consumption_id, "el consumo")
    return consumption_out(edit_consumption(db, row, user, body.quantity, body.reason))


@router.post("/consumptions/{consumption_id}/void")
def post_void_consumption(consumption_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    row = get_or_404(db, MaterialConsumption, consumption_id, "el consumo")
    return consumption_out(void_consumption(db, row, user, body.reason))


@router.get("/transfers")
def list_transfers(
    status: str | None = None,
    location_id: int | None = None,
    page_number: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(StockTransfer).order_by(StockTransfer.created_at.desc())
    if status:
        stmt = stmt.where(StockTransfer.status == status)
    rows = db.scalars(stmt).all()
    if location_id is not None:
        rows = [row for row in rows if row.from_location_id == location_id or row.to_location_id == location_id]
    return paginate([transfer_out(db, row) for row in rows], page_number, page_size)


@router.post("/transfers", status_code=201)
def post_transfer(body: TransferIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transfer = create_transfer(
        db,
        user,
        body.from_location_id,
        body.to_location_id,
        [item.model_dump() for item in body.items],
        body.notes,
        body.authorized_by_user_id,
        body.authorized_operational_name,
        body.authorized_at,
    )
    return transfer_out(db, transfer)


@router.get("/transfers/{transfer_id}")
def get_transfer(transfer_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return transfer_out(db, get_or_404(db, StockTransfer, transfer_id, "la transferencia"))


@router.post("/transfers/{transfer_id}/dispatch")
def post_dispatch(
    transfer_id: int,
    body: DispatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    transfer = get_or_404(db, StockTransfer, transfer_id, "la transferencia")
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, f"/transfers/{transfer_id}/dispatch", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    updated = dispatch_transfer(db, transfer, user, body.executed_by_user_id, body.executed_operational_name, body.executed_at)
    return _finish(db, user, idempotency_key or "", 200, transfer_out(db, updated))


@router.post("/transfers/{transfer_id}/receive")
def post_receive(
    transfer_id: int,
    body: ReceiveTransferIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    transfer = get_or_404(db, StockTransfer, transfer_id, "la transferencia")
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, f"/transfers/{transfer_id}/receive", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    updated = receive_transfer(
        db,
        transfer,
        user,
        [item.model_dump() for item in body.items],
        body.received_by_user_id,
        body.received_operational_name,
        body.close_with_difference,
        body.received_at,
        body.notes,
    )
    return _finish(db, user, idempotency_key or "", 200, transfer_out(db, updated))


@router.post("/transfers/{transfer_id}/cancel")
def post_cancel_transfer(transfer_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transfer = get_or_404(db, StockTransfer, transfer_id, "la transferencia")
    return transfer_out(db, cancel_transfer(db, transfer, user, body.reason))


@router.post("/transfers/{transfer_id}/void")
def post_void_transfer(transfer_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    transfer = get_or_404(db, StockTransfer, transfer_id, "la transferencia")
    return transfer_out(db, void_transfer(db, transfer, user, body.reason))


@router.post("/discrepancies/{discrepancy_id}/resolve")
def post_resolve(discrepancy_id: int, body: ResolveDiscrepancyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = get_or_404(db, TransferDiscrepancy, discrepancy_id, "la diferencia")
    resolve_discrepancy(db, row, user, body.action, body.reason)
    return transfer_out(db, row.item.transfer)


@router.get("/adjustments")
def list_adjustments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(InventoryAdjustment).order_by(InventoryAdjustment.occurred_at.desc())).all()
    return [adjustment_out(row) for row in rows]


@router.post("/adjustments", status_code=201)
def post_adjustment(
    body: AdjustmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    payload = body.model_dump(mode="json")
    replay = _replay(db, user, idempotency_key, "/adjustments", payload)
    if replay:
        return JSONResponse(status_code=replay["status"], content=replay["body"])
    row = register_adjustment(db, user, body.material_id, body.location_id, body.counted_qty, body.reason, body.occurred_at)
    return _finish(db, user, idempotency_key or "", 201, adjustment_out(row))


@router.patch("/adjustments/{adjustment_id}")
def patch_adjustment(adjustment_id: int, body: AdjustmentEdit, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    row = get_or_404(db, InventoryAdjustment, adjustment_id, "el ajuste")
    return adjustment_out(edit_adjustment(db, row, user, body.counted_qty, body.reason))


@router.post("/adjustments/{adjustment_id}/void")
def post_void_adjustment(adjustment_id: int, body: ReasonIn, db: Session = Depends(get_db), user: User = Depends(require_sysadmin)):
    row = get_or_404(db, InventoryAdjustment, adjustment_id, "el ajuste")
    return adjustment_out(void_adjustment(db, row, user, body.reason))


@router.get("/stock")
def get_stock(
    material_id: int | None = None,
    location_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = stock_rows(db, material_id, location_id, q)
    from app.api.presenters import _iso, _qty

    for row in rows:
        row["on_hand"] = _qty(row["on_hand"])
        row["pending_receipt"] = _qty(row["pending_receipt"])
        row["in_transit_out"] = _qty(row["in_transit_out"])
        row["in_transit_in"] = _qty(row["in_transit_in"])
        row["last_movement_at"] = _iso(row["last_movement_at"])
    return rows


@router.get("/stock/available")
def available(material_id: int, location_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    material = get_or_404(db, Material, material_id, "el material")
    get_or_404(db, Location, location_id, "la ubicación")
    return {"material_id": material_id, "location_id": location_id, "on_hand": format(get_on_hand(db, material.id, location_id), "f")}


@router.get("/movements")
def list_movements(
    material_id: int | None = None,
    location_id: int | None = None,
    movement_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import date

    start = date.fromisoformat(date_from) if date_from else None
    end = date.fromisoformat(date_to) if date_to else None
    rows = movements_query(db, material_id, location_id, movement_type, start, end, q)
    return paginate([movement_out(row) for row in rows], page_number, page_size)


@router.get("/stock/consistency")
def consistency(db: Session = Depends(get_db), _: User = Depends(require_sysadmin)):
    mismatches = consistency_report(db)
    return {"ok": len(mismatches) == 0, "mismatches": mismatches}


@router.get("/comparisons")
def comparisons(
    work_id: int | None = None,
    rubric_id: int | None = None,
    task_id: int | None = None,
    material_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import date

    from app.api.presenters import _qty

    rows = comparison_rows(
        db,
        work_id,
        rubric_id,
        task_id,
        material_id,
        date.fromisoformat(date_from) if date_from else None,
        date.fromisoformat(date_to) if date_to else None,
    )
    for row in rows:
        for key in (
            "executed_qty",
            "theoretical_qty",
            "real_qty",
            "absolute_difference",
            "stock_on_hand",
            "purchased_qty",
            "received_qty",
            "transferred_in",
            "transferred_out",
        ):
            row[key] = _qty(row[key])
        row["percent_deviation"] = None if row["percent_deviation"] is None else format(row["percent_deviation"], "f")
    return rows


@router.get("/comparisons/detail")
def comparison_detail(
    task_id: int,
    material_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import date

    from app.api.presenters import _iso, _qty

    data = investigation(
        db,
        task_id,
        material_id,
        date.fromisoformat(date_from) if date_from else None,
        date.fromisoformat(date_to) if date_to else None,
    )
    for row in data["theoretical_lines"]:
        row["execution_date"] = _iso(row["execution_date"])
        row["valid_from"] = _iso(row["valid_from"])
        for key in ("input_qty", "coefficient", "factor", "output_qty"):
            row[key] = _qty(row[key])
    for row in data["consumptions"]:
        row["quantity"] = _qty(row["quantity"])
        row["consumed_at"] = _iso(row["consumed_at"])
    return data


@router.get("/dashboard")
def get_dashboard(
    work_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import date

    from app.api.presenters import _iso, _qty

    data = dashboard(
        db,
        work_id,
        date.fromisoformat(date_from) if date_from else None,
        date.fromisoformat(date_to) if date_to else None,
    )
    data["theoretical_qty"] = _qty(data["theoretical_qty"]) if data["theoretical_qty"] is not None else None
    data["real_qty"] = _qty(data["real_qty"]) if data["real_qty"] is not None else None
    data["absolute_difference"] = _qty(data["absolute_difference"]) if data["absolute_difference"] is not None else None
    data["percent_deviation"] = None if data["percent_deviation"] is None else format(data["percent_deviation"], "f")
    for row in data["low_stock"]:
        row["on_hand"] = _qty(row["on_hand"])
        row["reorder_point"] = _qty(row["reorder_point"])
    for row in data["by_work"] + data["by_rubric"]:
        row["theoretical"] = _qty(row["theoretical"])
        row["real"] = _qty(row["real"])
    for row in data["top_deviations"]:
        for key in (
            "executed_qty",
            "theoretical_qty",
            "real_qty",
            "absolute_difference",
            "stock_on_hand",
            "purchased_qty",
            "received_qty",
            "transferred_in",
            "transferred_out",
        ):
            row[key] = _qty(row[key])
        row["percent_deviation"] = None if row["percent_deviation"] is None else format(row["percent_deviation"], "f")
    for row in data["evolution"]:
        row["theoretical"] = _qty(row["theoretical"])
        row["real"] = _qty(row["real"])
    for row in data["stock_by_location"]:
        row["on_hand"] = _qty(row["on_hand"])
    for row in data["recent_movements"]:
        row["occurred_at"] = _iso(row["occurred_at"])
        row["signed_qty"] = _qty(row["signed_qty"])
    return data


def _report_table(kind: str, db: Session, work_id: int | None, date_from: str | None, date_to: str | None):
    from datetime import date

    start = date.fromisoformat(date_from) if date_from else None
    end = date.fromisoformat(date_to) if date_to else None
    if kind == "teorico-real":
        rows = comparison_rows(db, work_id=work_id, date_from=start, date_to=end)
        headers = ["Obra", "Rubro", "Tarea", "Material", "Unidad", "Ejecutado", "Teórico", "Real", "Diferencia", "Desvío %"]
        table = [
            [
                row["work_name"],
                row["rubric_name"],
                row["task_name"],
                row["material_name"],
                row["unit_code"],
                format(row["executed_qty"], "f"),
                format(row["theoretical_qty"], "f"),
                format(row["real_qty"], "f"),
                format(row["absolute_difference"], "f"),
                "No calculable" if row["percent_deviation"] is None else format(row["percent_deviation"], "f"),
            ]
            for row in rows
        ]
        return headers, table, "Teorico vs real"
    if kind == "stock":
        rows = stock_rows(db)
        headers = ["Material", "Ubicación", "Stock disponible", "Último movimiento", "Fecha"]
        table = [
            [
                row["material_name"],
                row["location_name"],
                format(row["on_hand"], "f"),
                row["last_movement_type"] or "",
                row["last_movement_at"].isoformat() if row["last_movement_at"] else "",
            ]
            for row in rows
        ]
        return headers, table, "Stock"
    if kind == "ordenes":
        rows = purchase_report_rows(db, work_id)
        headers = ["Orden", "Proveedor", "Obra", "Fecha", "Material", "Pedido", "Recibido", "Pendiente", "Estado"]
        table = [
            [
                row["number"],
                row["supplier"],
                row["work"],
                row["date"].isoformat(),
                row["material"],
                format(row["qty_ordered"], "f"),
                format(row["qty_received"], "f"),
                format(row["qty_pending"], "f"),
                row["status"],
            ]
            for row in rows
        ]
        return headers, table, "Ordenes"
    if kind == "movimientos":
        rows = movements_query(db, None, None, None, start, end, None)
        headers = ["Fecha", "Material", "Tipo", "Ubicación", "Cantidad", "Responsable", "Referencia"]
        table = [
            [
                row.occurred_at.isoformat(),
                row.material.name,
                row.movement_type,
                row.location.name,
                format(row.signed_qty, "f"),
                row.recorded_by.full_name,
                row.reference_code or "",
            ]
            for row in rows
        ]
        return headers, table, "Movimientos"
    raise AppError(404, "Ese reporte no existe.")


@router.get("/reports/{kind}")
def report(
    kind: str,
    format: str = "json",
    work_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    headers, table, title = _report_table(kind, db, work_id, date_from, date_to)
    if format == "csv":
        content = rows_to_csv(headers, table)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})
    if format == "xlsx":
        content = rows_to_xlsx(headers, table, title)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{kind}.xlsx"'},
        )
    return {"headers": headers, "rows": table}


@router.get("/audit")
def list_audit(
    entity_type: str | None = None,
    page_number: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(AuditLog).order_by(AuditLog.at.desc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = db.scalars(stmt).all()
    payload = [
        {
            "id": row.id,
            "at": row.at.isoformat(),
            "user_name": row.user.full_name,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "before_json": row.before_json,
            "after_json": row.after_json,
            "reason": row.reason,
        }
        for row in rows
    ]
    return paginate(payload, page_number, page_size)
