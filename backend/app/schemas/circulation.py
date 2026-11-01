from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.domain.enums import FineStatus, LoanStatus, ReservationStatus
from app.schemas.common import ApiModel, cents_to_decimal
from app.schemas.members import MemberSummary


class BookRef(ApiModel):
    id: int
    title: str


class CopyRef(ApiModel):
    id: int
    inventory_code: str


class LoanCreate(ApiModel):
    card_number: str = Field(min_length=3, max_length=20, examples=["BIB-2026-0001"])
    inventory_code: str = Field(min_length=3, max_length=30, examples=["INV-00001-001"])


class LoanOut(ApiModel):
    id: int
    book: BookRef
    physical_copy: CopyRef
    member: MemberSummary
    loaned_at: datetime
    due_date: date
    returned_at: datetime | None
    renewals_count: int
    status: LoanStatus
    is_overdue: bool
    days_overdue: int

    @classmethod
    def from_entity(cls, loan, today: date) -> "LoanOut":
        is_overdue = loan.status == LoanStatus.ACTIVE and loan.due_date < today
        return cls(
            id=loan.id,
            book=BookRef(id=loan.copy.book.id, title=loan.copy.book.title),
            physical_copy=CopyRef(id=loan.copy.id, inventory_code=loan.copy.inventory_code),
            member=MemberSummary.model_validate(loan.member),
            loaned_at=loan.loaned_at,
            due_date=loan.due_date,
            returned_at=loan.returned_at,
            renewals_count=loan.renewals_count,
            status=loan.status,
            is_overdue=is_overdue,
            days_overdue=(today - loan.due_date).days if is_overdue else 0,
        )


class ReservationCreate(ApiModel):
    book_id: int
    member_id: int | None = Field(
        default=None, description="Solo personal de biblioteca; un socio reserva para sí mismo"
    )


class ReservationOut(ApiModel):
    id: int
    book: BookRef
    member: MemberSummary
    status: ReservationStatus
    created_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None
    physical_copy: CopyRef | None
    queue_position: int | None = Field(description="Posición en la cola (solo si está pendiente)")

    @classmethod
    def from_entity(cls, reservation, queue_position: int | None) -> "ReservationOut":
        return cls(
            id=reservation.id,
            book=BookRef.model_validate(reservation.book),
            member=MemberSummary.model_validate(reservation.member),
            status=reservation.status,
            created_at=reservation.created_at,
            ready_at=reservation.ready_at,
            expires_at=reservation.expires_at,
            physical_copy=CopyRef.model_validate(reservation.copy) if reservation.copy else None,
            queue_position=queue_position,
        )


class FineOut(ApiModel):
    id: int
    loan_id: int
    member: MemberSummary
    book_title: str
    days_late: int
    amount: Decimal
    status: FineStatus
    created_at: datetime
    paid_at: datetime | None

    @classmethod
    def from_entity(cls, fine) -> "FineOut":
        return cls(
            id=fine.id,
            loan_id=fine.loan_id,
            member=MemberSummary.model_validate(fine.member),
            book_title=fine.loan.copy.book.title,
            days_late=fine.days_late,
            amount=cents_to_decimal(fine.amount_cents),
            status=fine.status,
            created_at=fine.created_at,
            paid_at=fine.paid_at,
        )


class ReturnOut(ApiModel):
    loan: LoanOut
    fine: FineOut | None = None
    reserved_for: ReservationOut | None = Field(
        default=None, description="Reserva a la que quedó apartado el ejemplar devuelto"
    )


class ExpireHoldsOut(ApiModel):
    expired: int
