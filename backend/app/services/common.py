import hashlib
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import AppSetting, AuditLog, IdempotencyRecord, NumberSequence, User

BA = ZoneInfo("America/Argentina/Buenos_Aires")
Q4 = Decimal("0.0001")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_ba() -> date:
    return datetime.now(BA).date()


def as_qty(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Q4, rounding=ROUND_HALF_UP)


def assert_precision(value: Decimal, places: int, label: str) -> None:
    exponent = value.normalize().as_tuple().exponent
    if isinstance(exponent, int) and exponent < -places:
        raise AppError(422, f"{label} admite como máximo {places} decimales.")


def assert_positive(value: Decimal, label: str) -> None:
    if value <= 0:
        raise AppError(422, f"{label} debe ser mayor que cero.")


def assert_non_negative(value: Decimal, label: str) -> None:
    if value < 0:
        raise AppError(422, f"{label} no puede ser negativo.")


def require_user(user: User | None) -> User:
    if user is None or user.id is None:
        raise AppError(422, "La operación tiene que identificar a la persona responsable.")
    return user


def require_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if len(text) < 3:
        raise AppError(422, "Indicá un motivo de al menos 3 caracteres.")
    return text


def get_or_404(db: Session, model, entity_id: int, label: str):
    obj = db.get(model, entity_id)
    if obj is None:
        raise AppError(404, f"No se encontró {label}.")
    return obj


def ensure_active(entity, label: str) -> None:
    if hasattr(entity, "is_active") and not entity.is_active:
        raise AppError(422, f"{label} está inactivo.")


def audit(
    db: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict | None,
    after: dict | None,
    reason: str | None = None,
) -> None:
    db.add(
        AuditLog(
            at=now_utc(),
            user_id=user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
            after_json=json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
            reason=reason,
        )
    )


def setting_bool(db: Session, key: str) -> bool:
    row = db.get(AppSetting, key)
    return bool(row and row.value.strip().lower() == "true")


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def next_number(db: Session, prefix: str) -> str:
    row = db.get(NumberSequence, prefix)
    if row is None:
        row = NumberSequence(name=prefix, last_value=0)
        db.add(row)
        db.flush()
    row.last_value += 1
    db.flush()
    return f"{prefix}-{row.last_value:05d}"


def period_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    start = None
    end = None
    if date_from is not None:
        start = datetime.combine(date_from, time.min, tzinfo=BA).astimezone(timezone.utc)
    if date_to is not None:
        end = datetime.combine(date_to, time.max, tzinfo=BA).astimezone(timezone.utc)
    if start is not None and end is not None and start > end:
        raise AppError(422, "La fecha inicial no puede ser posterior a la final.")
    return start, end


def version_moment(value: date) -> datetime:
    local = datetime.combine(value, time.max, tzinfo=BA)
    return local.astimezone(timezone.utc)


def json_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def begin_idempotency(db: Session, user: User, key: str | None, path: str, payload: dict) -> dict | None:
    token = (key or "").strip()
    if not token:
        raise AppError(400, "Falta el encabezado Idempotency-Key para esta operación.")
    if len(token) > 80:
        raise AppError(400, "La clave de reintento es demasiado larga.")
    digest = json_hash(payload)
    existing = db.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.key == token, IdempotencyRecord.user_id == user.id)
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise AppError(409, "Esa clave de reintento ya se usó con otros datos.")
        if not existing.response_body:
            raise AppError(409, "Esa operación ya se está procesando.")
        return {"status": existing.response_status, "body": json.loads(existing.response_body)}
    db.add(
        IdempotencyRecord(
            key=token,
            user_id=user.id,
            path=path,
            request_hash=digest,
            response_status=0,
            response_body=None,
            created_at=now_utc(),
        )
    )
    db.flush()
    return None


def finish_idempotency(db: Session, user: User, key: str, status: int, body: dict) -> None:
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == key.strip(), IdempotencyRecord.user_id == user.id
        )
    )
    if existing is None:
        return
    existing.response_status = status
    existing.response_body = json.dumps(body, ensure_ascii=False, default=str)


def user_brief(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role}
