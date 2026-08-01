"""Modelos Pydantic para auth: requests/responses de los endpoints /auth/*."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

Role = Literal["dueño", "operario", "repartidor"]

# Coincide con VARCHAR(255) de las columnas email/name en el schema — sin
# esto, un valor más largo pasaba la validación de Pydantic y recién
# explotaba como 500 al llegar al INSERT en Postgres, en vez de un 422
# limpio de "campo demasiado largo".
_EMAIL_MAX = 255
_NAME_MAX = 255
# Bug real (Ronda 21, ciclo nuevo, dueño): no había ninguna longitud mínima
# de contraseña en todo el stack (ni backend ni los <input type="password">
# del frontend) — un dueño podía crear su cuenta (o invitar a su equipo) con
# una contraseña de un solo carácter, sin ningún aviso. Se aplica solo en
# los dos puntos donde se ESTABLECE una contraseña nueva (registro, invitar
# equipo) — no en LoginRequest, que solo verifica una ya existente y no debe
# romper el login de cuentas creadas antes de este fix.
_PASSWORD_MIN = 8


class RegisterRequest(BaseModel):
    account_name: str = Field(max_length=_NAME_MAX)
    email: str = Field(max_length=_EMAIL_MAX)
    password: str = Field(min_length=_PASSWORD_MIN)
    full_name: Optional[str] = Field(default=None, max_length=_NAME_MAX)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    account_id: str


class CreateUserRequest(BaseModel):
    email: str = Field(max_length=_EMAIL_MAX)
    password: str = Field(min_length=_PASSWORD_MIN)
    full_name: Optional[str] = Field(default=None, max_length=_NAME_MAX)
    role: Role


class UserOut(BaseModel):
    id: str
    account_id: str
    email: str
    role: Role
    full_name: Optional[str] = None


class TeamMemberOut(BaseModel):
    """Miembro del equipo de la cuenta, para la pantalla de gestión (Etapa A)."""
    id: str
    email: str
    role: Role
    full_name: Optional[str] = None
    active: bool


class SetUserActiveRequest(BaseModel):
    active: bool
