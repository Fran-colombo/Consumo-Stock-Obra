from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def _dec(value: Decimal) -> str:
    return format(value, "f")


Qty = Annotated[Decimal, PlainSerializer(_dec, return_type=str)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
        raise ValueError("El correo no es válido.")
    return email


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)


class UserIn(BaseModel):
    email: str
    username: str | None = Field(default=None, min_length=3, max_length=80)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    role: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = None
    is_active: bool | None = None


class UnitIn(BaseModel):
    code: str
    name: str
    decimal_places: int = 4


class UnitUpdate(BaseModel):
    name: str | None = None
    decimal_places: int | None = None


class WorkIn(BaseModel):
    name: str
    code: str
    address: str | None = None
    status: str = "ACTIVA"
    start_date: date | None = None
    notes: str | None = None


class WorkUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None
    status: str | None = None
    start_date: date | None = None
    notes: str | None = None


class LocationIn(BaseModel):
    name: str
    code: str
    location_type: str
    work_id: int | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    location_type: str | None = None
    work_id: int | None = None
    is_active: bool | None = None


class RubricIn(BaseModel):
    name: str
    code: str
    description: str | None = None


class RubricUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    is_active: bool | None = None
    coverage_unit_id: int | None = None
    waste_percent: Decimal | None = None


class RecipeLineIn(BaseModel):
    material_id: int
    coefficient: Decimal


class TaskParameterValueIn(BaseModel):
    parameter_id: int
    value: Decimal | None = None


class RubricTaskIn(BaseModel):
    work_id: int
    formula_id: int
    parameters: list[TaskParameterValueIn]
    waste_percent: Decimal | None = None


class FormulaIn(BaseModel):
    name: str


class FormulaUpdate(BaseModel):
    name: str | None = None
    waste_percent: Decimal | None = None
    is_active: bool | None = None
    measure_unit_id: int | None = None
    notes: str | None = None


class FormulaParameterIn(BaseModel):
    name: str
    unit_id: int
    counts: bool = True
    role: str | None = None
    factor: Decimal | None = None


class FormulaLineIn(BaseModel):
    material_id: int
    coefficient: Decimal


class MaterialIn(BaseModel):
    name: str
    code: str
    unit_id: int
    category: str | None = None
    description: str | None = None
    notes: str | None = None
    reorder_point: Decimal | None = None


class MaterialUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    unit_id: int | None = None
    category: str | None = None
    description: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    reorder_point: Decimal | None = None


class ConversionIn(BaseModel):
    material_id: int
    from_unit_id: int
    to_unit_id: int
    factor: Decimal
    notes: str | None = None


class TaskIn(BaseModel):
    work_id: int
    rubric_id: int
    name: str
    description: str | None = None
    unit_id: int
    planned_qty: Decimal | None = None
    execution_start: date | None = None
    execution_end: date | None = None
    status: str = "PENDIENTE"
    notes: str | None = None


class TaskUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rubric_id: int | None = None
    unit_id: int | None = None
    planned_qty: Decimal | None = None
    execution_start: date | None = None
    execution_end: date | None = None
    status: str | None = None
    notes: str | None = None
    pending_reason: str | None = None
    waste_percent: Decimal | None = None


class ExecutionIn(BaseModel):
    quantity_delta: Decimal | None = None
    new_total: Decimal | None = None
    execution_date: date | None = None
    notes: str | None = None
    corrects_execution_id: int | None = None
    consume_materials: bool = False


class ExecutionEdit(BaseModel):
    quantity_delta: Decimal
    reason: str


class ReasonIn(BaseModel):
    reason: str


class RuleIn(BaseModel):
    material_id: int
    coefficient: Decimal
    output_unit_id: int | None = None
    reference_unit_id: int | None = None
    reason: str | None = None


class RuleVersionIn(BaseModel):
    coefficient: Decimal
    output_unit_id: int | None = None
    reference_unit_id: int | None = None
    reason: str


class SupplierIn(BaseModel):
    name: str
    contact: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None
    is_active: bool | None = None


class OrderItemIn(BaseModel):
    material_id: int
    quantity: Decimal
    unit_price: Decimal | None = None
    currency: str | None = None


class OrderIn(BaseModel):
    supplier_id: int
    destination_location_id: int
    work_id: int | None = None
    expected_date: date | None = None
    notes: str | None = None
    items: list[OrderItemIn]


class OrderUpdate(BaseModel):
    supplier_id: int | None = None
    destination_location_id: int | None = None
    work_id: int | None = None
    expected_date: date | None = None
    notes: str | None = None
    items: list[OrderItemIn] | None = None


class OrderItemQty(BaseModel):
    quantity: Decimal
    reason: str | None = None


class ReceiptItemIn(BaseModel):
    purchase_order_item_id: int
    quantity: Decimal


class ReceiptIn(BaseModel):
    location_id: int
    received_at: datetime | None = None
    notes: str | None = None
    items: list[ReceiptItemIn]


class ReceiptCorrectionIn(BaseModel):
    reason: str
    received_at: datetime | None = None
    items: list[ReceiptItemIn]


class ReceiptItemEdit(BaseModel):
    quantity: Decimal
    reason: str


class ConsumptionIn(BaseModel):
    work_id: int
    task_id: int
    location_id: int
    material_id: int
    quantity: Decimal
    consumed_at: datetime | None = None
    notes: str | None = None


class ConsumptionCorrectionIn(BaseModel):
    quantity: Decimal
    reason: str
    consumed_at: datetime | None = None


class ConsumptionEdit(BaseModel):
    quantity: Decimal
    reason: str


class TransferItemIn(BaseModel):
    material_id: int
    quantity: Decimal


class DirectTransferIn(BaseModel):
    from_location_id: int
    to_location_id: int
    material_id: int
    quantity: Decimal
    received_quantity: Decimal | None = None
    shortfall_action: str | None = None
    reason: str | None = None


class ArriveIn(BaseModel):
    quantity: Decimal | None = None


class UseOrderIn(BaseModel):
    task_id: int


class TransferIn(BaseModel):
    from_location_id: int
    to_location_id: int
    notes: str | None = None
    items: list[TransferItemIn]
    authorized_by_user_id: int | None = None
    authorized_operational_name: str | None = None
    authorized_at: datetime | None = None


class DispatchIn(BaseModel):
    executed_by_user_id: int | None = None
    executed_operational_name: str | None = None
    executed_at: datetime | None = None


class ReceiveLineIn(BaseModel):
    transfer_item_id: int
    quantity: Decimal


class ReceiveTransferIn(BaseModel):
    items: list[ReceiveLineIn]
    received_by_user_id: int | None = None
    received_operational_name: str | None = None
    close_with_difference: bool = False
    received_at: datetime | None = None
    notes: str | None = None


class ResolveDiscrepancyIn(BaseModel):
    action: str
    reason: str


class AdjustmentIn(BaseModel):
    material_id: int
    location_id: int
    counted_qty: Decimal
    reason: str
    occurred_at: datetime | None = None


class AdjustmentEdit(BaseModel):
    counted_qty: Decimal
    reason: str


class SettingsUpdate(BaseModel):
    allow_negative_stock: bool | None = None
    allow_over_receipt: bool | None = None
