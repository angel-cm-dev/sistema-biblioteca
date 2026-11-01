"""Reglas de negocio puras (sin base de datos ni HTTP).

Mantener estas reglas como funciones puras permite probarlas con pruebas unitarias
instantáneas y leerlas como si fueran el reglamento de la biblioteca.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import MemberType


@dataclass(frozen=True, slots=True)
class LoanPolicy:
    """Condiciones de préstamo según el tipo de socio."""

    max_active_loans: int
    loan_days: int
    max_renewals: int


# Por qué valores distintos: los docentes usan libros para preparar cursos completos (más
# tiempo y más ejemplares); los externos no tienen vínculo institucional, así que el riesgo de
# no devolución es mayor y se les da menos margen.
LOAN_POLICIES: dict[MemberType, LoanPolicy] = {
    MemberType.STUDENT: LoanPolicy(max_active_loans=3, loan_days=14, max_renewals=2),
    MemberType.TEACHER: LoanPolicy(max_active_loans=10, loan_days=30, max_renewals=3),
    MemberType.EXTERNAL: LoanPolicy(max_active_loans=2, loan_days=7, max_renewals=1),
}


def policy_for(member_type: MemberType) -> LoanPolicy:
    return LOAN_POLICIES[MemberType(member_type)]


def due_date_for(start: date, member_type: MemberType) -> date:
    return start + timedelta(days=policy_for(member_type).loan_days)


def days_late(due: date, returned_on: date) -> int:
    """Días de retraso. Devolver el mismo día del vencimiento no genera multa."""
    return max(0, (returned_on - due).days)


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def fine_amount_cents(days: int, fine_per_day: Decimal) -> int:
    """Multa = días de retraso x tarifa diaria. Se guarda en céntimos para evitar errores de
    redondeo de punto flotante con dinero."""
    return days * to_cents(fine_per_day)


def is_blocked_by_debt(pending_debt_cents: int, threshold: Decimal) -> bool:
    """El socio queda bloqueado cuando su deuda pendiente alcanza el umbral configurado.

    Un umbral de 0 significa "cualquier deuda bloquea"."""
    threshold_cents = to_cents(threshold)
    if threshold_cents == 0:
        return pending_debt_cents > 0
    return pending_debt_cents >= threshold_cents


def renewal_rejection_reason(
    *,
    member_type: MemberType,
    renewals_done: int,
    is_overdue: bool,
    has_pending_reservations: bool,
) -> str | None:
    """Devuelve el motivo por el que NO se puede renovar, o None si la renovación procede.

    El orden de validación importa: se informa primero la causa más "dura".
    """
    if is_overdue:
        return "No se puede renovar un préstamo vencido; devuélvalo y regularice la multa"
    if has_pending_reservations:
        # Renovar con gente en cola sería injusto: el libro nunca volvería a circular.
        return "Hay socios en cola de reserva para este libro; no se permite renovar"
    if renewals_done >= policy_for(member_type).max_renewals:
        return "Se alcanzó el número máximo de renovaciones para su tipo de socio"
    return None
