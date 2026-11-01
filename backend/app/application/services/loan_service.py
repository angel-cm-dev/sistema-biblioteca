"""Casos de uso de préstamo, devolución y renovación."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.pagination import Page, PageParams
from app.application.services.member_service import MemberService
from app.application.services.reservation_service import ReservationService
from app.core.config import Settings
from app.domain import policies
from app.domain.clock import Clock
from app.domain.enums import CopyStatus, LoanStatus, ReservationStatus
from app.domain.errors import BusinessRuleError, ConflictError, NotFoundError
from app.infrastructure.models import Fine, Loan, Reservation
from app.infrastructure.repositories.catalog import CatalogRepository
from app.infrastructure.repositories.circulation import (
    FineRepository,
    LoanRepository,
    ReservationRepository,
)
from app.infrastructure.repositories.members import MemberRepository


@dataclass(slots=True)
class ReturnResult:
    loan: Loan
    fine: Fine | None
    reserved_for: Reservation | None


class LoanService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self.loans = LoanRepository(session)
        self.fines = FineRepository(session)
        self.catalog = CatalogRepository(session)
        self.members = MemberRepository(session)
        self.reservation_repo = ReservationRepository(session)
        self.reservations = ReservationService(session, settings, clock)
        self.member_service = MemberService(session, settings, clock)

    def get(self, loan_id: int, actor: Actor) -> Loan:
        loan = self.loans.get(loan_id)
        if not loan:
            raise NotFoundError("Préstamo no encontrado")
        actor.ensure_owns(loan.member_id)
        return loan

    def list(
        self,
        params: PageParams,
        *,
        actor: Actor,
        member_id: int | None,
        status: LoanStatus | None,
        overdue: bool | None,
        q: str | None,
    ) -> Page[Loan]:
        scoped = actor.scope_member_id()
        return self.loans.list(
            params,
            today=self.clock.today(),
            member_id=scoped or member_id,
            status=status,
            overdue=overdue,
            q=q,
        )

    # ---- Préstamo -----------------------------------------------------------------------
    def checkout(self, *, card_number: str, inventory_code: str) -> Loan:
        # Antes de prestar, liberamos apartados vencidos para no bloquear ejemplares.
        self.reservations.expire_holds()

        member = self.members.get_by_card(card_number)
        if not member:
            raise NotFoundError(f"No existe un socio con carnet {card_number}")
        copy = self.catalog.get_copy_by_code(inventory_code)
        if not copy:
            raise NotFoundError(f"No existe el ejemplar {inventory_code}")

        reservation_to_fulfill: Reservation | None = None
        if copy.status == CopyStatus.ON_HOLD:
            hold = self.reservation_repo.ready_for_copy(copy.id)
            if not hold or hold.member_id != member.id:
                raise ConflictError(
                    "El ejemplar está apartado para otro socio con reserva",
                    code="copy_on_hold",
                )
            reservation_to_fulfill = hold
        elif copy.status != CopyStatus.AVAILABLE:
            raise ConflictError(
                f"El ejemplar no está disponible (estado: {copy.status})",
                code="copy_unavailable",
            )

        standing = self.member_service.standing(member)
        if standing.block_reasons:
            raise BusinessRuleError(
                "El socio no puede recibir préstamos: " + "; ".join(standing.block_reasons),
                code="member_blocked",
            )
        if standing.active_loans >= standing.policy.max_active_loans:
            raise BusinessRuleError(
                f"Límite de {standing.policy.max_active_loans} préstamos simultáneos alcanzado "
                f"para socios de tipo '{member.member_type}'",
                code="loan_limit_reached",
            )
        if self.loans.member_has_active_loan_of_book(member.id, copy.book_id):
            # Evita que un socio acapare varios ejemplares del mismo título.
            raise BusinessRuleError(
                "El socio ya tiene un ejemplar de este libro", code="same_title_on_loan"
            )

        now = self.clock.now()
        loan = Loan(
            copy_id=copy.id,
            member_id=member.id,
            loaned_at=now,
            due_date=policies.due_date_for(self.clock.today(), member.member_type),
            renewals_count=0,
            status=LoanStatus.ACTIVE,
        )
        copy.status = CopyStatus.LOANED

        # Si el socio tenía una reserva (lista o pendiente) de este libro, queda atendida.
        open_reservation = reservation_to_fulfill or self.reservation_repo.open_for_member_and_book(
            member.id, copy.book_id
        )
        if open_reservation:
            open_reservation.status = ReservationStatus.FULFILLED
            open_reservation.closed_at = now
            open_reservation.copy_id = copy.id

        self.loans.add(loan)
        self.session.commit()
        return self.loans.get(loan.id)

    # ---- Devolución ---------------------------------------------------------------------
    def return_loan(self, loan_id: int) -> ReturnResult:
        loan = self.loans.get(loan_id)
        if not loan:
            raise NotFoundError("Préstamo no encontrado")
        if loan.status != LoanStatus.ACTIVE:
            raise ConflictError("El préstamo ya fue devuelto", code="already_returned")

        now = self.clock.now()
        loan.returned_at = now
        loan.status = LoanStatus.RETURNED

        fine = None
        late = policies.days_late(loan.due_date, self.clock.today())
        if late > 0:
            # La multa se genera al devolver: hasta entonces la deuda sigue creciendo y el
            # préstamo vencido ya bloquea nuevos préstamos por sí mismo.
            fine = self.fines.add(
                Fine(
                    loan_id=loan.id,
                    member_id=loan.member_id,
                    days_late=late,
                    amount_cents=policies.fine_amount_cents(late, self.settings.fine_per_day),
                    created_at=now,
                )
            )
        self.session.flush()
        reserved_for = self.reservations.route_copy(loan.copy)
        self.session.commit()
        if fine:
            fine = self.fines.get(fine.id)
        if reserved_for:
            reserved_for = self.reservation_repo.get(reserved_for.id)
        return ReturnResult(loan=self.loans.get(loan.id), fine=fine, reserved_for=reserved_for)

    # ---- Renovación ---------------------------------------------------------------------
    def renew(self, loan_id: int, actor: Actor) -> Loan:
        loan = self.get(loan_id, actor)
        if loan.status != LoanStatus.ACTIVE:
            raise ConflictError("Solo se pueden renovar préstamos activos", code="not_active")

        member = loan.member
        reason = policies.renewal_rejection_reason(
            member_type=member.member_type,
            renewals_done=loan.renewals_count,
            is_overdue=loan.due_date < self.clock.today(),
            has_pending_reservations=self.reservation_repo.has_pending_for_book(loan.copy.book_id),
        )
        if reason:
            raise BusinessRuleError(reason, code="renewal_not_allowed")
        debt = self.fines.pending_debt_cents(member.id)
        if policies.is_blocked_by_debt(debt, self.settings.debt_block_threshold):
            raise BusinessRuleError(
                "El socio está bloqueado por deuda pendiente", code="member_blocked"
            )

        # Se extiende desde el vencimiento actual: renovar antes no "regala" ni "quita" días.
        loan.due_date = loan.due_date + timedelta(
            days=policies.policy_for(member.member_type).loan_days
        )
        loan.renewals_count += 1
        self.session.commit()
        return self.loans.get(loan.id)
