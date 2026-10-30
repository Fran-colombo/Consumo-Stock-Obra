import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.routes import router
from app.core.config import BACKEND_DIR, get_settings
from app.core import database
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.entities import AppSetting, UnitOfMeasure, User
from app.models.enums import UserRole
from app.services.common import now_utc

UNITS = [
    ("kg", "Kilogramo", 3),
    ("bolsa", "Bolsa", 0),
    ("m3", "Metro cúbico", 3),
    ("m2", "Metro cuadrado", 3),
    ("m", "Metro", 3),
    ("cm", "Centímetro", 2),
    ("l", "Litro", 3),
    ("u", "Unidad", 0),
]


def setup_logging() -> None:
    log_dir = BACKEND_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )


def run_migrations() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")


def ensure_reference_data(db) -> None:
    for code, name, places in UNITS:
        exists = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == code))
        if exists is None:
            db.add(UnitOfMeasure(code=code, name=name, decimal_places=places))
    for key in ("allow_negative_stock", "allow_over_receipt"):
        if db.get(AppSetting, key) is None:
            db.add(AppSetting(key=key, value="false"))


def configured_admin_email(settings) -> str:
    raw = (settings.sysadmin_email or "").strip()
    if not raw and "@" in (settings.sysadmin_user or ""):
        raw = settings.sysadmin_user
    if not raw:
        return ""
    from app.schemas import normalize_email

    return normalize_email(raw)


def ensure_sysadmin(db) -> None:
    settings = get_settings()
    try:
        email = configured_admin_email(settings)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    existing = db.scalar(select(User).where(User.role == UserRole.SYSADMIN.value).order_by(User.id))
    if existing is not None:
        if email and not existing.email:
            taken = db.scalar(select(User).where(User.email == email, User.id != existing.id))
            if taken is None:
                existing.email = email
                if settings.sysadmin_password and len(settings.sysadmin_password) >= 8:
                    existing.password_hash = hash_password(settings.sysadmin_password)
                logging.getLogger(__name__).info("Administrador listo para ingresar con %s", email)
        return
    if db.scalar(select(func.count()).select_from(User)):
        return
    if not email or not settings.sysadmin_password or not settings.sysadmin_name:
        raise RuntimeError(
            "No hay usuarios. Definí CONKRETO_SYSADMIN_EMAIL, CONKRETO_SYSADMIN_PASSWORD y CONKRETO_SYSADMIN_NAME."
        )
    if len(settings.sysadmin_password) < 8:
        raise RuntimeError("La clave inicial del administrador debe tener al menos 8 caracteres.")
    username = settings.sysadmin_user.strip().lower() or email
    db.add(
        User(
            username=username,
            email=email,
            full_name=settings.sysadmin_name.strip(),
            password_hash=hash_password(settings.sysadmin_password),
            role=UserRole.SYSADMIN.value,
            is_active=True,
            created_at=now_utc(),
        )
    )


def init_database() -> None:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("Falta CONKRETO_JWT_SECRET.")
    data_dir = BACKEND_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        raw = settings.database_url.removeprefix("sqlite:///")
        if raw.startswith("./"):
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
        elif raw.startswith("/"):
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
    database.get_engine()
    run_migrations()
    if database.SessionLocal is None:
        raise RuntimeError("No se pudo abrir la base de datos.")
    db = database.SessionLocal()
    try:
        ensure_reference_data(db)
        ensure_sysadmin(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    try:
        init_database()
    except Exception:
        logging.getLogger("conkreto").exception("No se pudo iniciar la base")
        raise
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Conkreto", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": "Revisá los datos ingresados.", "errors": exc.errors()},
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_request: Request, exc: IntegrityError):
        logging.getLogger("conkreto").warning("Integridad: %s", exc)
        return JSONResponse(status_code=409, content={"detail": "El registro entra en conflicto con datos existentes."})

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception):
        logging.getLogger("conkreto").exception("Error no controlado")
        return JSONResponse(status_code=500, content={"detail": "Ocurrió un error interno. El detalle quedó en el registro."})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(router, prefix="/api")
    return app


app = create_app()
