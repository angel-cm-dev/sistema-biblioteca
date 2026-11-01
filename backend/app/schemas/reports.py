from decimal import Decimal

from app.domain.enums import MemberType
from app.schemas.common import ApiModel
from app.schemas.members import MemberSummary


class SummaryOut(ApiModel):
    books: int
    copies: int
    available_copies: int
    members: int
    active_loans: int
    overdue_loans: int
    pending_reservations: int
    pending_fines: Decimal


class TopBookOut(ApiModel):
    book_id: int
    title: str
    isbn: str
    loans: int


class DelinquentMember(MemberSummary):
    member_type: MemberType
    email: str


class DelinquencyOut(ApiModel):
    member: DelinquentMember
    pending_debt: Decimal
    overdue_loans: int
    max_days_overdue: int
    is_blocked: bool
