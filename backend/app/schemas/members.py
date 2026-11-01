from datetime import datetime
from decimal import Decimal

from pydantic import EmailStr, Field, field_validator

from app.domain.enums import MemberType
from app.schemas.auth import PASSWORD_RULE, validate_password_strength
from app.schemas.common import ApiModel


class MemberBase(ApiModel):
    full_name: str = Field(min_length=3, max_length=120, examples=["Lucía Quispe Mamani"])
    email: EmailStr
    document_id: str = Field(
        pattern=r"^\d{8,12}$", description="DNI (8 dígitos) o carné de extranjería"
    )
    phone: str | None = Field(default=None, pattern=r"^\+?\d{6,15}$")
    member_type: MemberType

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return " ".join(value.split())


class MemberCreate(MemberBase):
    password: str | None = Field(
        default=None,
        max_length=72,
        description=f"Opcional: crea una cuenta de acceso para el socio. {PASSWORD_RULE}",
    )

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str | None) -> str | None:
        return validate_password_strength(value) if value else None


class MemberUpdate(ApiModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?\d{6,15}$")
    member_type: MemberType | None = None
    is_active: bool | None = None


class MemberSummary(ApiModel):
    id: int
    card_number: str
    full_name: str


class MemberOut(MemberSummary):
    email: str
    document_id: str
    phone: str | None
    member_type: MemberType
    is_active: bool
    created_at: datetime


class LoanPolicyOut(ApiModel):
    max_active_loans: int
    loan_days: int
    max_renewals: int


class MemberStatusOut(ApiModel):
    member: MemberOut
    policy: LoanPolicyOut
    active_loans: int
    overdue_loans: int
    pending_debt: Decimal
    is_blocked: bool
    block_reasons: list[str]
    can_borrow: bool
