"""Modelos Pydantic para auth: requests/responses de los endpoints /auth/*."""

from typing import Literal, Optional
from pydantic import BaseModel

Role = Literal["dueño", "operario", "repartidor"]


class RegisterRequest(BaseModel):
    account_name: str
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    account_id: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Role


class UserOut(BaseModel):
    id: str
    account_id: str
    email: str
    role: Role
    full_name: Optional[str] = None
