"""
Auth: hashing de contraseñas y tokens JWT.

Funciones puras, sin acceso a base de datos — los endpoints (backend_python/api)
y las dependencies (backend_python/auth/dependencies.py) las usan junto con
PostgreSQLAdapter para el CRUD real de usuarios/cuentas.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend_python.config import get_config

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(user_id: str, account_id: str, role: str) -> str:
    config = get_config()
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "account_id": account_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Retorna el payload si el token es válido y no expiró, None si no."""
    config = get_config()
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        return None


__all__ = ["hash_password", "verify_password", "create_access_token", "decode_access_token"]
