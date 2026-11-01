from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.application.pagination import Page, PageParams
from app.domain.enums import MemberType
from app.infrastructure.models import Member
from app.infrastructure.repositories.base import apply_sort, paginate


class MemberRepository:
    SORTABLE = {
        "full_name": Member.full_name,
        "card_number": Member.card_number,
        "member_type": Member.member_type,
        "created_at": Member.created_at,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, member_id: int) -> Member | None:
        return self.session.get(Member, member_id)

    def get_by_card(self, card_number: str) -> Member | None:
        return self.session.scalar(
            select(Member).where(Member.card_number == card_number.strip().upper())
        )

    def exists_with(
        self, *, email: str, document_id: str, exclude_id: int | None = None
    ) -> str | None:
        """Devuelve el nombre del campo duplicado ('email' o 'document_id') o None."""
        stmt = select(Member).where(
            or_(Member.email == email.lower(), Member.document_id == document_id)
        )
        if exclude_id:
            stmt = stmt.where(Member.id != exclude_id)
        found = self.session.scalar(stmt.limit(1))
        if not found:
            return None
        return "email" if found.email == email.lower() else "document_id"

    def next_card_sequence(self) -> int:
        return (self.session.scalar(select(func.max(Member.id))) or 0) + 1

    def list(
        self,
        params: PageParams,
        *,
        q: str | None,
        member_type: MemberType | None,
        is_active: bool | None,
    ) -> Page[Member]:
        stmt = select(Member)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Member.full_name.ilike(like),
                    Member.card_number.ilike(like),
                    Member.email.ilike(like),
                    Member.document_id.ilike(like),
                )
            )
        if member_type:
            stmt = stmt.where(Member.member_type == member_type)
        if is_active is not None:
            stmt = stmt.where(Member.is_active == is_active)
        stmt = apply_sort(stmt, params.sort, self.SORTABLE, Member.id)
        return paginate(self.session, stmt, params)

    def add(self, member: Member) -> Member:
        self.session.add(member)
        self.session.flush()
        return member
