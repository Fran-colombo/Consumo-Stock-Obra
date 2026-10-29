from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_engine = None
SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args, poolclass=NullPool, future=True)

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _connection_record):
        if engine.dialect.name == "sqlite":
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    @event.listens_for(engine, "begin")
    def _begin(conn):
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def get_engine():
    global _engine, SessionLocal
    if _engine is None:
        _engine = _make_engine(get_settings().database_url)
        SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    return _engine


def reset_engine() -> None:
    global _engine, SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
