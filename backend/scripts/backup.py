"""Copia consistente de la base SQLite, aunque la aplicación esté abierta."""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings


def database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise SystemExit("Este script copia la base SQLite local.")
    raw = url.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path


def backup(destination: Path | None = None) -> Path:
    source = database_path()
    if not source.exists():
        raise SystemExit(f"No existe la base {source}.")
    target_dir = BACKEND_DIR / "data" / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = destination or target_dir / f"conkreto-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()
    return target


def restore(backup_file: Path) -> None:
    source = database_path()
    if not backup_file.exists():
        raise SystemExit("No se encontró el archivo de backup.")
    print("Detené la API antes de restaurar. Se va a reemplazar la base actual.")
    incoming = sqlite3.connect(backup_file)
    target = sqlite3.connect(source)
    try:
        incoming.backup(target)
    finally:
        target.close()
        incoming.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup o restauración de la base de Conkreto.")
    parser.add_argument("--restore", type=Path, help="Archivo .db a restaurar. La API tiene que estar detenida.")
    args = parser.parse_args()
    if args.restore:
        restore(args.restore)
        print(f"Base restaurada en {database_path()}")
        return
    path = backup()
    print(f"Backup guardado en {path}")


if __name__ == "__main__":
    main()
