"""Consultas agregadas para reportes y dashboard (solo lectura)."""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import CopyStatus, FineStatus, LoanStatus, ReservationStatus
from app.infrastructure.models import Book, Copy, Fine, Loan, Member, Reservation


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _count(self, stmt) -> int:
        return self.session.scalar(stmt) or 0

    def summary(self, today: date) -> dict[str, int]:
        return {
            "books": self._count(select(func.count(Book.id))),
            "copies": self._count(select(func.count(Copy.id))),
            "available_copies": self._count(
                select(func.count(Copy.id)).where(Copy.status == CopyStatus.AVAILABLE)
            ),
            "members": self._count(select(func.count(Member.id)).where(Member.is_active)),
            "active_loans": self._count(
                select(func.count(Loan.id)).where(Loan.status == LoanStatus.ACTIVE)
            ),
            "overdue_loans": self._count(
                select(func.count(Loan.id)).where(
                    Loan.status == LoanStatus.ACTIVE, Loan.due_date < today
                )
            ),
            "pending_reservations": self._count(
                select(func.count(Reservation.id)).where(
                    Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.READY])
                )
            ),
            "pending_fines_cents": self._count(
                select(func.coalesce(func.sum(Fine.amount_cents), 0)).where(
                    Fine.status == FineStatus.PENDING
                )
            ),
        }

    def most_borrowed(
        self, *, limit: int, date_from: datetime | None, date_to: datetime | None
    ) -> list[tuple[int, str, str, int]]:
        stmt = (
            select(Book.id, Book.title, Book.isbn, func.count(Loan.id).label("loans"))
            .join(Copy, Copy.book_id == Book.id)
            .join(Loan, Loan.copy_id == Copy.id)
            .group_by(Book.id, Book.title, Book.isbn)
            .order_by(func.count(Loan.id).desc(), Book.title)
            .limit(limit)
        )
        if date_from:
            stmt = stmt.where(Loan.loaned_at >= date_from)
        if date_to:
            stmt = stmt.where(Loan.loaned_at < date_to)
        return [tuple(row) for row in self.session.execute(stmt)]

    def delinquency(self, today: date) -> list[dict]:
        """Socios morosos: con deuda pendiente o con préstamos vencidos sin devolver."""
        debt = (
            select(Fine.member_id, func.sum(Fine.amount_cents).label("debt_cents"))
            .where(Fine.status == FineStatus.PENDING)
            .group_by(Fine.member_id)
            .subquery()
        )
        overdue = (
            select(
                Loan.member_id,
                func.count(Loan.id).label("overdue_loans"),
                func.min(Loan.due_date).label("oldest_due"),
            )
            .where(Loan.status == LoanStatus.ACTIVE, Loan.due_date < today)
            .group_by(Loan.member_id)
            .subquery()
        )
        stmt = (
            select(
                Member,
                func.coalesce(debt.c.debt_cents, 0),
                func.coalesce(overdue.c.overdue_loans, 0),
                overdue.c.oldest_due,
            )
            .outerjoin(debt, debt.c.member_id == Member.id)
            .outerjoin(overdue, overdue.c.member_id == Member.id)
            .where((debt.c.debt_cents > 0) | (overdue.c.overdue_loans > 0))
        )
        rows = []
        for member, debt_cents, overdue_loans, oldest_due in self.session.execute(stmt):
            max_days = (today - oldest_due).days if oldest_due else 0
            rows.append(
                {
                    "member": member,
                    "pending_debt_cents": int(debt_cents),
                    "overdue_loans": int(overdue_loans),
                    "max_days_overdue": max_days,
                }
            )
        rows.sort(key=lambda r: (r["pending_debt_cents"], r["max_days_overdue"]), reverse=True)
        return rows
