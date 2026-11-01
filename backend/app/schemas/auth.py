import re

from pydantic import EmailStr, Field, field_validator

from app.domain.enums import Role
from app.schemas.common import ApiModel

PASSWORD_RULE = "Mínimo 8 caracteres, con al menos una mayúscula, una minúscula y un número"


def validate_password_strength(value: str) -> str:
    if (
        len(value) < 8
        or not re.search(r"[A-Z]", value)
        or not re.search(r"[a-z]", value)
        or not re.search(r"\d", value)
    ):
        raise ValueError(PASSWORD_RULE)
    if len(value.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede exceder 72 bytes")
    return value


class LoginIn(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(ApiModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    member_id: int | None = None


class TokenOut(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(ApiModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    password: str = Field(max_length=72, description=PASSWORD_RULE)
    role: Role
    member_id: int | None = Field(default=None, description="Obligatorio si el rol es 'socio'")

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return validate_password_strength(value)
