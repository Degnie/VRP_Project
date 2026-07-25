"""
FastAPI dependencies para auth: extraer y validar el usuario actual desde el
JWT del header Authorization, y restringir endpoints por rol.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend_python.auth import decode_access_token
from backend_python.persistence.postgres_adapter import PostgreSQLAdapter

_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """Usuario autenticado, extraído del JWT — no pega a la DB de nuevo."""

    def __init__(self, user_id: str, account_id: str, role: str):
        self.user_id = user_id
        self.account_id = account_id
        self.role = role


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return CurrentUser(
        user_id=payload["sub"],
        account_id=payload["account_id"],
        role=payload["role"],
    )


def require_role(*roles: str):
    """Factory de dependency: rechaza con 403 si el usuario no tiene uno de los roles dados."""

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user

    return _check


__all__ = ["CurrentUser", "get_current_user", "require_role"]
