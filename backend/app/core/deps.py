from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.entities import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AppError(401, "Tenés que iniciar sesión para continuar.")
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise AppError(401, "La sesión no es válida o expiró.")
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise AppError(401, "La sesión no es válida o expiró.")
    return user


def require_sysadmin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.SYSADMIN.value:
        raise AppError(403, "Solo el administrador del sistema puede modificar registros ya confirmados.")
    return user
