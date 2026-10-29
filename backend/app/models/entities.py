from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

QTY = Numeric(18, 4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    decimal_places: Mapped[int] = mapped_column(Integer, default=4)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(40))


class NumberSequence(Base):
    __tablename__ = "number_sequences"

    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    address: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVA", index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    locations: Mapped[list["Location"]] = relationship(back_populates="work")
    tasks: Mapped[list["Task"]] = relationship(back_populates="work")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    location_type: Mapped[str] = mapped_column(String(20), index=True)
    work_id: Mapped[int | None] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    work: Mapped[Work | None] = relationship(back_populates="locations")


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), index=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    planned_qty: Mapped[Decimal | None] = mapped_column(QTY, nullable=True)
    execution_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    execution_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDIENTE", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    work: Mapped[Work] = relationship(back_populates="tasks")
    rubric: Mapped[Rubric] = relationship()
    unit: Mapped[UnitOfMeasure] = relationship()


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(QTY)
    execution_date: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    corrects_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_executions.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMADO", index=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = relationship()
    lines: Mapped[list["TheoreticalConsumptionLine"]] = relationship(back_populates="execution")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reorder_point: Mapped[Decimal | None] = mapped_column(QTY, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    unit: Mapped[UnitOfMeasure] = relationship()


class MaterialUnitConversion(Base):
    __tablename__ = "material_unit_conversions"
    __table_args__ = (UniqueConstraint("material_id", "from_unit_id", "to_unit_id", name="uq_conversion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    from_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    to_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    factor: Mapped[Decimal] = mapped_column(QTY)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    material: Mapped[Material] = relationship()
    from_unit: Mapped[UnitOfMeasure] = relationship(foreign_keys=[from_unit_id])
    to_unit: Mapped[UnitOfMeasure] = relationship(foreign_keys=[to_unit_id])


class ConsumptionRule(Base):
    __tablename__ = "consumption_rules"
    __table_args__ = (UniqueConstraint("task_id", "material_id", name="uq_rule_task_material"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = relationship()
    material: Mapped[Material] = relationship()
    versions: Mapped[list["ConsumptionRuleVersion"]] = relationship(back_populates="rule")


class ConsumptionRuleVersion(Base):
    __tablename__ = "consumption_rule_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("consumption_rules.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(40))
    coefficient: Mapped[Decimal] = mapped_column(QTY)
    reference_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    output_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped[ConsumptionRule] = relationship(back_populates="versions")
    reference_unit: Mapped[UnitOfMeasure] = relationship(foreign_keys=[reference_unit_id])
    output_unit: Mapped[UnitOfMeasure] = relationship(foreign_keys=[output_unit_id])


class TheoreticalConsumptionLine(Base):
    __tablename__ = "theoretical_consumption_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_execution_id: Mapped[int] = mapped_column(ForeignKey("task_executions.id", ondelete="RESTRICT"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    rule_version_id: Mapped[int] = mapped_column(ForeignKey("consumption_rule_versions.id", ondelete="RESTRICT"))
    coefficient_snapshot: Mapped[Decimal] = mapped_column(QTY)
    method_snapshot: Mapped[str] = mapped_column(String(40))
    input_qty: Mapped[Decimal] = mapped_column(QTY)
    output_qty: Mapped[Decimal] = mapped_column(QTY)
    output_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    conversion_factor_snapshot: Mapped[Decimal] = mapped_column(QTY)

    execution: Mapped[TaskExecution] = relationship(back_populates="lines")
    material: Mapped[Material] = relationship()
    rule_version: Mapped[ConsumptionRuleVersion] = relationship()


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (UniqueConstraint("material_id", "location_id", name="uq_stock_material_location"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    on_hand: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))

    material: Mapped[Material] = relationship()
    location: Mapped[Location] = relationship()


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    signed_qty: Mapped[Decimal] = mapped_column(QTY)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    document_type: Mapped[str] = mapped_column(String(40))
    document_id: Mapped[int] = mapped_column(Integer, index=True)
    reference_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMADO", index=True)
    corrects_movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_movements.id", ondelete="RESTRICT"), nullable=True
    )
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    material: Mapped[Material] = relationship()
    location: Mapped[Location] = relationship()
    recorded_by: Mapped[User] = relationship(foreign_keys=[recorded_by_user_id])


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    contact: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"))
    work_id: Mapped[int | None] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=True, index=True)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="BORRADOR", index=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    supplier: Mapped[Supplier] = relationship()
    work: Mapped[Work | None] = relationship()
    destination: Mapped[Location] = relationship()
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="order")
    created_by: Mapped[User] = relationship()


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (UniqueConstraint("purchase_order_id", "material_id", name="uq_po_material"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    qty_ordered: Mapped[Decimal] = mapped_column(QTY)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()
    unit: Mapped[UnitOfMeasure] = relationship()


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    received_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMADO", index=True)
    corrects_receipt_id: Mapped[int | None] = mapped_column(
        ForeignKey("goods_receipts.id", ondelete="RESTRICT"), nullable=True
    )
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    order: Mapped[PurchaseOrder] = relationship()
    location: Mapped[Location] = relationship()
    received_by: Mapped[User] = relationship(foreign_keys=[received_by_user_id])
    items: Mapped[list["GoodsReceiptItem"]] = relationship(back_populates="receipt")


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id", ondelete="RESTRICT"), index=True)
    purchase_order_item_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_items.id", ondelete="RESTRICT"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    excedente: Mapped[bool] = mapped_column(Boolean, default=False)
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id"), nullable=True)

    receipt: Mapped[GoodsReceipt] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()
    order_item: Mapped[PurchaseOrderItem] = relationship()


class MaterialConsumption(Base):
    __tablename__ = "material_consumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMADO", index=True)
    corrects_consumption_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_consumptions.id", ondelete="RESTRICT"), nullable=True
    )
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id"), nullable=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    work: Mapped[Work] = relationship()
    task: Mapped[Task] = relationship()
    location: Mapped[Location] = relationship()
    material: Mapped[Material] = relationship()
    recorded_by: Mapped[User] = relationship(foreign_keys=[recorded_by_user_id])
    movement: Mapped[InventoryMovement | None] = relationship()


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    from_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    to_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(40), default="REGISTRADA", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    authorized_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    authorized_operational_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    executed_operational_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    received_operational_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    origin: Mapped[Location] = relationship(foreign_keys=[from_location_id])
    destination: Mapped[Location] = relationship(foreign_keys=[to_location_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    items: Mapped[list["StockTransferItem"]] = relationship(back_populates="transfer")


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"
    __table_args__ = (UniqueConstraint("transfer_id", "material_id", name="uq_transfer_material"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("stock_transfers.id", ondelete="RESTRICT"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    qty_sent: Mapped[Decimal] = mapped_column(QTY)
    qty_received: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    qty_returned: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"))
    out_movement_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id"), nullable=True)
    in_movement_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id"), nullable=True)

    transfer: Mapped[StockTransfer] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()
    unit: Mapped[UnitOfMeasure] = relationship()


class TransferDiscrepancy(Base):
    __tablename__ = "transfer_discrepancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_item_id: Mapped[int] = mapped_column(ForeignKey("stock_transfer_items.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(QTY)
    status: Mapped[str] = mapped_column(String(20), default="PENDIENTE", index=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    item: Mapped[StockTransferItem] = relationship()


class InventoryAdjustment(Base):
    __tablename__ = "inventory_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    previous_qty: Mapped[Decimal] = mapped_column(QTY)
    counted_qty: Mapped[Decimal] = mapped_column(QTY)
    difference: Mapped[Decimal] = mapped_column(QTY)
    reason: Mapped[str] = mapped_column(Text)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMADO", index=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    material: Mapped[Material] = relationship()
    location: Mapped[Location] = relationship()
    recorded_by: Mapped[User] = relationship(foreign_keys=[recorded_by_user_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship()


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("key", "user_id", name="uq_idempotency_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    path: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer, default=0)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
