from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_prefix="CONKRETO_",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'conkreto.db').as_posix()}"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    sysadmin_user: str = ""
    sysadmin_password: str = ""
    sysadmin_name: str = ""
    cors_origins: str = "http://localhost:8087,http://127.0.0.1:8087"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
