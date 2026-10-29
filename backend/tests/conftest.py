import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = tmp_path / "conkreto.db"
    monkeypatch.setenv("CONKRETO_DATABASE_URL", f"sqlite:///{database.as_posix()}")
    monkeypatch.setenv("CONKRETO_JWT_SECRET", "test-secret-test-secret")
    monkeypatch.setenv("CONKRETO_SYSADMIN_USER", "admin")
    monkeypatch.setenv("CONKRETO_SYSADMIN_EMAIL", "admin@conkreto.local")
    monkeypatch.setenv("CONKRETO_SYSADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.setenv("CONKRETO_SYSADMIN_NAME", "Administrador")
    monkeypatch.setenv("CONKRETO_CORS_ORIGINS", "http://localhost:5173")
    from app.core.config import get_settings
    from app.core.database import reset_engine

    get_settings.cache_clear()
    reset_engine()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    get_settings.cache_clear()
