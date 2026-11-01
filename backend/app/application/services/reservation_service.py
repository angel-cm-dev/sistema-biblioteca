"""Reservas con cola FIFO.

Reglas:
- Se reserva un LIBRO (no un ejemplar) y solo cuando no hay ejemplares disponibles: si hay uno
  en estantería, lo correcto es pedir el préstamo directamente.
- La cola se atiende en orden de llegada (created_at, id).
- Cuando un ejemplar vuelve a circular (devolución, alta de ejemplar, fin de mantenimiento o
  reserva cancelada/expirada) se aparta para el primero de la cola durante
  `reservation_hold_days`. Si no lo recoge a tiempo, la reserva expira y pasa al siguiente.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.pagination import Page, PageParams
from app.core.config import Settings
from app.domain import policies
from app.domain.clock import Clock
from app.domain.enums import CopyStatus, ReservationStatus
from app.domain.errors import BusinessRuleError, ConflictError, NotFoundError
from app.infrastructure.models import Copy, Reservation
from app.infrastructure.repositories.catalog import CatalogRepository
from app.infrastructure.repositories.circulation import (
    FineRepository,
    LoanRepository,
    ReservationRepository,
)
from app.infrastructure.repositories.members import MemberRepository


class ReservationService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self.repo = ReservationRepository(session)
        self.catalog = CatalogRepository(session)
        self.members = MemberRepository(session)
        self.loans = LoanRepository(session)
        self.fines = FineRepository(session)

    # ---- Cola ---------------------------------------------------------------------------
    def route_copy(self, copy: Copy) -> Reservation | None:
        """Decide el destino de un ejemplar que vuelve a circular.

        Devuelve la reserva a la que quedó apartado o None si quedó disponible.
        No hace commit: lo llama otra operación que controla la transacción.
        """
        queue = self.repo.queue_for_book(copy.book_id)
        if not queue:
            copy.status = CopyStatus.AVAILABLE
            return None
        first = queue[0]
        now = self.clock.now()
        first.status = ReservationStatus.READY
        first.copy_id = copy.id
        first.ready_at = now
        first.expires_at = now + timedelta(days=self.settings.reservation_hold_days)
        copy.status = CopyStatus.ON_HOLD
        self.session.flush()
        return first

    def expire_holds(self) -> int:
        """Expira reservas 'lista' no recogidas a tiempo y pasa el ejemplar al siguiente.

        Se ejecuta de forma perezosa antes de operaciones de circulación y también se expone
        como endpoint (en producción lo dispararía un job programado, p.ej. cron).
        """
        now = self.clock.now()
        expired = self.repo.expired_holds(now)
        for reservation in expired:
            reservation.status = ReservationStatus.EXPIRED
            reservation.closed_at = now
            copy = self.catalog.get_copy(reservation.copy_id) if reservation.copy_id else None
            self.session.flush()
            if copy:
                self.route_copy(copy)
        if expired:
            self.session.commit()
        return len(expired)

    # ---- Casos de uso -------------------------------------------------------------------
    def create(self, *, book_id: int, member_id: int | None, actor: Actor) -> Reservation:
        self.expire_holds()
        if not actor.is_staff:
            member_id = actor.member_id  # un socio siempre reserva para sí mismo
        if member_id is None:
            raise BusinessRuleError("Debe indicar el socio para la reserva")
        member = self.members.get(member_id)
        if not member:
            raise NotFoundError("Socio no encontrado")
        book = self.catalog.get_book(book_id)
        if not book:
            raise NotFoundError("Libro no encontrado")

        if not member.is_active:
            raise BusinessRuleError("El socio está inactivo", code="member_inactive")
        debt = self.fines.pending_debt_cents(member.id)
        if policies.is_blocked_by_debt(debt, self.settings.debt_block_threshold):
            raise BusinessRuleError(
                "El socio está bloqueado por deuda pendiente", code="member_blocked"
            )
        if self.repo.open_for_member_and_book(member.id, book.id):
            raise ConflictError("Ya tiene una reserva activa para este libro", code="duplicate")
        if self.loans.member_has_active_loan_of_book(member.id, book.id):
            raise BusinessRuleError("Ya tiene este libro en préstamo", code="already_loaned")
        if self.catalog.count_available_copies(book.id) > 0:
            raise BusinessRuleError(
                "Hay ejemplares disponibles: solicite el préstamo en mostrador",
                code="copies_available",
            )

        reservation = Reservation(
            book_id=book.id,
            member_id=member.id,
            status=ReservationStatus.PENDING,
            created_at=self.clock.now(),
        )
        self.repo.add(reservation)
        self.session.commit()
        return self.repo.get(reservation.id)

    def cancel(self, reservation_id: int, actor: Actor) -> Reservation:
        reservation = self.get(reservation_id, actor)
        if reservation.status not in (ReservationStatus.PENDING, ReservationStatus.READY):
            raise ConflictError(f"La reserva ya está '{reservation.status}'", code="not_open")
        was_ready = reservation.status == ReservationStatus.READY
        reservation.status = ReservationStatus.CANCELLED
        reservation.closed_at = self.clock.now()
        self.session.flush()
        copy = self.catalog.get_copy(reservation.copy_id) if reservation.copy_id else None
        if was_ready and copy:
            # El ejemplar apartado se libera y pasa al siguiente de la cola.
            self.route_copy(copy)
        self.session.commit()
        return reservation

    def get(self, reservation_id: int, actor: Actor) -> Reservation:
        reservation = self.repo.get(reservation_id)
        if not reservation:
            raise NotFoundError("Reserva no encontrada")
        actor.ensure_owns(reservation.member_id)
        return reservation

    def list(
        self,
        params: PageParams,
        *,
        actor: Actor,
        member_id: int | None,
        book_id: int | None,
        status: ReservationStatus | None,
    ) -> Page[Reservation]:
        scoped = actor.scope_member_id()
        return self.repo.list(params, member_id=scoped or member_id, book_id=book_id, status=status)

    def queue_position(self, reservation: Reservation) -> int | None:
        return self.repo.queue_position(reservation)
