"""Repositorios de circulación: préstamos, reservas y multas."""

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.application.pagination import Page, PageParams
from app.domain.enums import FineStatus, LoanStatus, ReservationStatus
from app.infrastructure.models import Book, Copy, Fine, Loan, Member, Reservation
from app.infrastructure.repositories.base import apply_sort, paginate

OPEN_RESERVATION_STATES = (ReservationStatus.PENDING, ReservationStatus.READY)


class LoanRepository:
    SORTABLE = {"loaned_at": Loan.loaned_at, "due_date": Loan.due_date, "status": Loan.status}

    def __init__(self, session: Session) -> None:
        self.session = session

    def _query(self):
        return select(Loan).options(
            joinedload(Loan.copy).joinedload(Copy.book), joinedload(Loan.member)
        )

    def get(self, loan_id: int) -> Loan | None:
        return self.session.scalar(self._query().where(Loan.id == loan_id))

    def add(self, loan: Loan) -> Loan:
        self.session.add(loan)
        self.session.flush()
        return loan

    def count_active(self, member_id: int) -> int:
        return (
            self.session.scalar(
                select(func.count(Loan.id)).where(
                    Loan.member_id == member_id, Loan.status == LoanStatus.ACTIVE
                )
            )
            or 0
        )

    def count_overdue(self, member_id: int, today: date) -> int:
        return (
            self.session.scalar(
                select(func.count(Loan.id)).where(
                    Loan.member_id == member_id,
                    Loan.status == LoanStatus.ACTIVE,
                    Loan.due_date < today,
                )
            )
            or 0
        )

    def member_has_active_loan_of_book(self, member_id: int, book_id: int) -> bool:
        stmt = (
            select(Loan.id)
            .join(Copy, Copy.id == Loan.copy_id)
            .where(
                Loan.member_id == member_id,
                Loan.status == LoanStatus.ACTIVE,
                Copy.book_id == book_id,
            )
        )
        return self.session.scalar(stmt.limit(1)) is not None

    def list(
        self,
        params: PageParams,
        *,
        today: date,
        member_id: int | None,
        status: LoanStatus | None,
        overdue: bool | None,
        q: str | None,
    ) -> Page[Loan]:
        stmt = self._query().join(Loan.copy).join(Copy.book).join(Loan.member)
        if member_id:
            stmt = stmt.where(Loan.member_id == member_id)
        if status:
            stmt = stmt.where(Loan.status == status)
        if overdue is True:
            stmt = stmt.where(Loan.status == LoanStatus.ACTIVE, Loan.due_date < today)
        elif overdue is False:
            stmt = stmt.where(or_(Loan.status != LoanStatus.ACTIVE, Loan.due_date >= today))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Book.title.ilike(like),
                    Copy.inventory_code.ilike(like),
                    Member.full_name.ilike(like),
                    Member.card_number.ilike(like),
                )
            )
        stmt = apply_sort(stmt, params.sort or "-loaned_at", self.SORTABLE, Loan.id.desc())
        return paginate(self.session, stmt, params)


class ReservationRepository:
    SORTABLE = {"created_at": Reservation.created_at, "status": Reservation.status}

    def __init__(self, session: Session) -> None:
        self.session = session

    def _query(self):
        return select(Reservation).options(
            joinedload(Reservation.book),
            joinedload(Reservation.member),
            joinedload(Reservation.copy),
        )

    def get(self, reservation_id: int) -> Reservation | None:
        return self.session.scalar(self._query().where(Reservation.id == reservation_id))

    def add(self, reservation: Reservation) -> Reservation:
        self.session.add(reservation)
        self.session.flush()
        return reservation

    def queue_for_book(self, book_id: int) -> list[Reservation]:
        """Cola FIFO de reservas pendientes: el más antiguo primero (id desempata)."""
        return list(
            self.session.scalars(
                select(Reservation)
                .where(
                    Reservation.book_id == book_id,
                    Reservation.status == ReservationStatus.PENDING,
                )
                .order_by(Reservation.created_at, Reservation.id)
            )
        )

    def has_pending_for_book(self, book_id: int) -> bool:
        return bool(self.queue_for_book(book_id))

    def open_for_member_and_book(self, member_id: int, book_id: int) -> Reservation | None:
        return self.session.scalar(
            select(Reservation).where(
                Reservation.member_id == member_id,
                Reservation.book_id == book_id,
                Reservation.status.in_(OPEN_RESERVATION_STATES),
            )
        )

    def ready_for_copy(self, copy_id: int) -> Reservation | None:
        return self.session.scalar(
            select(Reservation).where(
                Reservation.copy_id == copy_id, Reservation.status == ReservationStatus.READY
            )
        )

    def expired_holds(self, now: datetime) -> list[Reservation]:
        return list(
            self.session.scalars(
                select(Reservation).where(
                    Reservation.status == ReservationStatus.READY, Reservation.expires_at < now
                )
            )
        )

    def list(
        self,
        params: PageParams,
        *,
        member_id: int | None,
        book_id: int | None,
        status: ReservationStatus | None,
    ) -> Page[Reservation]:
        stmt = self._query()
        if member_id:
            stmt = stmt.where(Reservation.member_id == member_id)
        if book_id:
            stmt = stmt.where(Reservation.book_id == book_id)
        if status:
            stmt = stmt.where(Reservation.status == status)
        stmt = apply_sort(stmt, params.sort or "-created_at", self.SORTABLE, Reservation.id)
        return paginate(self.session, stmt, params)

    def queue_position(self, reservation: Reservation) -> int | None:
        if reservation.status != ReservationStatus.PENDING:
            return None
        ids = [r.id for r in self.queue_for_book(reservation.book_id)]
        return ids.index(reservation.id) + 1 if reservation.id in ids else None


class FineRepository:
    SORTABLE = {
        "created_at": Fine.created_at,
        "amount": Fine.amount_cents,
        "status": Fine.status,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, fine_id: int) -> Fine | None:
        return self.session.scalar(
            select(Fine)
            .options(joinedload(Fine.member), joinedload(Fine.loan).joinedload(Loan.copy))
            .where(Fine.id == fine_id)
        )

    def add(self, fine: Fine) -> Fine:
        self.session.add(fine)
        self.session.flush()
        return fine

    def pending_debt_cents(self, member_id: int) -> int:
        return (
            self.session.scalar(
                select(func.coalesce(func.sum(Fine.amount_cents), 0)).where(
                    Fine.member_id == member_id, Fine.status == FineStatus.PENDING
                )
            )
            or 0
        )

    def list(
        self,
        params: PageParams,
        *,
        member_id: int | None,
        status: FineStatus | None,
    ) -> Page[Fine]:
        stmt = select(Fine).options(
            joinedload(Fine.member),
            joinedload(Fine.loan).joinedload(Loan.copy).joinedload(Copy.book),
        )
        if member_id:
            stmt = stmt.where(Fine.member_id == member_id)
        if status:
            stmt = stmt.where(Fine.status == status)
        stmt = apply_sort(stmt, params.sort or "-created_at", self.SORTABLE, Fine.id)
        return paginate(self.session, stmt, params)
