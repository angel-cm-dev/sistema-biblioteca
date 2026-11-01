"""Pruebas de la lógica de negocio de circulación usando servicios + SQLite en memoria."""

from decimal import Decimal

import pytest

from app.application.actor import Actor
from app.application.services.fine_service import FineService
from app.domain.enums import CopyStatus, FineStatus, LoanStatus, MemberType, ReservationStatus, Role
from app.domain.errors import BusinessRuleError, ConflictError, PermissionDeniedError
from tests.factories import Factory

# ---- Préstamos y límites ------------------------------------------------------------------


def test_checkout_sets_due_date_and_marks_copy_loaned(factory: Factory, clock):
    member = factory.member(MemberType.STUDENT)
    book = factory.book(copies=1)

    loan = factory.lend(member, book)

    assert loan.status == LoanStatus.ACTIVE
    assert (loan.due_date - clock.today()).days == 14
    assert loan.copy.status == CopyStatus.LOANED


@pytest.mark.parametrize(
    ("member_type", "limit"),
    [(MemberType.STUDENT, 3), (MemberType.EXTERNAL, 2)],
)
def test_loan_limit_per_member_type(factory: Factory, member_type, limit):
    member = factory.member(member_type)
    books = [factory.book() for _ in range(limit + 1)]
    for book in books[:limit]:
        factory.lend(member, book)

    with pytest.raises(BusinessRuleError) as exc:
        factory.lend(member, books[limit])
    assert exc.value.code == "loan_limit_reached"


def test_cannot_lend_a_copy_that_is_already_loaned(factory: Factory):
    book = factory.book(copies=1)
    factory.lend(factory.member(), book)
    with pytest.raises(ConflictError):
        factory.lend(factory.member(), book)


def test_member_cannot_hold_two_copies_of_same_book(factory: Factory):
    member = factory.member()
    book = factory.book(copies=2)
    factory.lend(member, book, 0)
    with pytest.raises(BusinessRuleError) as exc:
        factory.lend(member, book, 1)
    assert exc.value.code == "same_title_on_loan"


def test_overdue_loan_blocks_new_loans(factory: Factory, clock):
    member = factory.member(MemberType.EXTERNAL)
    factory.lend(member, factory.book())
    clock.advance(days=8)  # externo: 7 días
    with pytest.raises(BusinessRuleError) as exc:
        factory.lend(member, factory.book())
    assert "vencidos" in exc.value.detail


# ---- Devoluciones y multas ----------------------------------------------------------------


def test_on_time_return_creates_no_fine(factory: Factory, clock):
    member = factory.member()
    loan = factory.lend(member, factory.book())
    clock.advance(days=14)  # justo el día de vencimiento

    result = factory.loans.return_loan(loan.id)

    assert result.fine is None
    assert result.loan.status == LoanStatus.RETURNED
    assert result.loan.copy.status == CopyStatus.AVAILABLE


def test_late_return_creates_fine_per_day(factory: Factory, clock):
    member = factory.member()
    loan = factory.lend(member, factory.book())
    clock.advance(days=14 + 4)

    result = factory.loans.return_loan(loan.id)

    assert result.fine is not None
    assert result.fine.days_late == 4
    assert result.fine.amount_cents == 400
    assert result.fine.status == FineStatus.PENDING


def test_cannot_return_twice(factory: Factory):
    loan = factory.lend(factory.member(), factory.book())
    factory.loans.return_loan(loan.id)
    with pytest.raises(ConflictError):
        factory.loans.return_loan(loan.id)


def test_debt_over_threshold_blocks_and_payment_unblocks(
    factory: Factory, clock, session, settings
):
    member = factory.member()
    loan = factory.lend(member, factory.book())
    clock.advance(days=14 + 10)  # 10 días tarde = S/ 10 = umbral
    fine = factory.loans.return_loan(loan.id).fine

    standing = factory.members.standing(member)
    assert standing.is_blocked and not standing.can_borrow
    with pytest.raises(BusinessRuleError) as exc:
        factory.lend(member, factory.book())
    assert exc.value.code == "member_blocked"

    FineService(session, settings, clock).pay(fine.id)
    assert factory.members.standing(member).can_borrow
    factory.lend(member, factory.book())


def test_debt_below_threshold_does_not_block(factory: Factory, clock):
    member = factory.member()
    loan = factory.lend(member, factory.book())
    clock.advance(days=14 + 3)
    factory.loans.return_loan(loan.id)

    standing = factory.members.standing(member)
    assert standing.pending_debt_cents == 300
    assert not standing.is_blocked


def test_threshold_is_configurable(factory: Factory, clock, settings):
    settings.debt_block_threshold = Decimal("2.00")
    member = factory.member()
    loan = factory.lend(member, factory.book())
    clock.advance(days=14 + 3)
    factory.loans.return_loan(loan.id)
    assert factory.members.standing(member).is_blocked


# ---- Renovaciones -------------------------------------------------------------------------


def test_renewal_extends_from_current_due_date(factory: Factory, clock):
    member = factory.member()
    loan = factory.lend(member, factory.book())
    original_due = loan.due_date
    actor = Actor(user_id=1, role=Role.LIBRARIAN)

    clock.advance(days=5)
    renewed = factory.loans.renew(loan.id, actor)

    assert renewed.renewals_count == 1
    assert (renewed.due_date - original_due).days == 14


def test_renewal_limit(factory: Factory):
    member = factory.member(MemberType.EXTERNAL)  # máximo 1 renovación
    loan = factory.lend(member, factory.book())
    actor = Actor(user_id=1, role=Role.LIBRARIAN)
    factory.loans.renew(loan.id, actor)
    with pytest.raises(BusinessRuleError) as exc:
        factory.loans.renew(loan.id, actor)
    assert "máximo" in exc.value.detail


def test_renewal_blocked_when_book_has_pending_reservation(factory: Factory):
    holder, waiting = factory.member(), factory.member()
    book = factory.book(copies=1)
    loan = factory.lend(holder, book)
    factory.reserve(waiting, book)

    with pytest.raises(BusinessRuleError) as exc:
        factory.loans.renew(loan.id, Actor(user_id=1, role=Role.LIBRARIAN))
    assert "cola" in exc.value.detail


def test_renewal_rejected_when_overdue(factory: Factory, clock):
    loan = factory.lend(factory.member(), factory.book())
    clock.advance(days=15)
    with pytest.raises(BusinessRuleError):
        factory.loans.renew(loan.id, Actor(user_id=1, role=Role.LIBRARIAN))


def test_member_cannot_renew_someone_elses_loan(factory: Factory):
    owner = factory.member()
    other = factory.member()
    loan = factory.lend(owner, factory.book())
    with pytest.raises(PermissionDeniedError):
        factory.loans.renew(loan.id, Actor(user_id=9, role=Role.MEMBER, member_id=other.id))


# ---- Reservas y cola FIFO -----------------------------------------------------------------


def test_cannot_reserve_when_copies_available(factory: Factory):
    with pytest.raises(BusinessRuleError) as exc:
        factory.reserve(factory.member(), factory.book(copies=1))
    assert exc.value.code == "copies_available"


def test_duplicate_reservation_rejected(factory: Factory):
    book = factory.book(copies=1)
    factory.lend(factory.member(), book)
    member = factory.member()
    factory.reserve(member, book)
    with pytest.raises(ConflictError):
        factory.reserve(member, book)


def test_return_assigns_copy_to_first_in_queue_fifo(factory: Factory, clock):
    book = factory.book(copies=1)
    holder = factory.member()
    first, second = factory.member(), factory.member()
    loan = factory.lend(holder, book)
    r1 = factory.reserve(first, book)
    clock.advance(hours=1)
    r2 = factory.reserve(second, book)
    assert factory.reservations.queue_position(r1) == 1
    assert factory.reservations.queue_position(r2) == 2

    result = factory.loans.return_loan(loan.id)

    assert result.reserved_for.id == r1.id
    assert result.reserved_for.status == ReservationStatus.READY
    assert result.loan.copy.status == CopyStatus.ON_HOLD
    # El segundo sigue en cola, ahora en la posición 1
    assert factory.reservations.queue_position(r2) == 1


def test_copy_on_hold_only_lendable_to_reserving_member(factory: Factory, session):
    book = factory.book(copies=1)
    holder, waiting, intruder = factory.member(), factory.member(), factory.member()
    loan = factory.lend(holder, book)
    reservation = factory.reserve(waiting, book)
    factory.loans.return_loan(loan.id)

    with pytest.raises(ConflictError) as exc:
        factory.lend(intruder, book)
    assert exc.value.code == "copy_on_hold"

    new_loan = factory.lend(waiting, book)
    session.refresh(reservation)
    assert new_loan.status == LoanStatus.ACTIVE
    assert reservation.status == ReservationStatus.FULFILLED


def test_expired_hold_passes_to_next_in_queue(factory: Factory, clock, session):
    book = factory.book(copies=1)
    holder, first, second = factory.member(), factory.member(), factory.member()
    loan = factory.lend(holder, book)
    r1 = factory.reserve(first, book)
    clock.advance(hours=1)
    r2 = factory.reserve(second, book)
    factory.loans.return_loan(loan.id)

    clock.advance(days=4)  # se aparta por 3 días
    assert factory.reservations.expire_holds() == 1

    session.refresh(r1)
    session.refresh(r2)
    assert r1.status == ReservationStatus.EXPIRED
    assert r2.status == ReservationStatus.READY
    assert r2.copy_id == loan.copy_id


def test_cancelling_ready_reservation_releases_copy(factory: Factory, session):
    book = factory.book(copies=1)
    holder, first = factory.member(), factory.member()
    loan = factory.lend(holder, book)
    reservation = factory.reserve(first, book)
    factory.loans.return_loan(loan.id)

    factory.reservations.cancel(
        reservation.id, Actor(user_id=1, role=Role.MEMBER, member_id=first.id)
    )

    session.refresh(book)
    assert book.copies[0].status == CopyStatus.AVAILABLE


def test_blocked_member_cannot_reserve(factory: Factory, clock):
    member = factory.member()
    loan = factory.lend(member, factory.book())
    clock.advance(days=14 + 12)
    factory.loans.return_loan(loan.id)

    book = factory.book(copies=1)
    factory.lend(factory.member(), book)
    with pytest.raises(BusinessRuleError) as exc:
        factory.reserve(member, book)
    assert exc.value.code == "member_blocked"


def test_copy_back_from_maintenance_goes_to_queue(factory: Factory, session):
    book = factory.book(copies=2)
    factory.catalog.change_copy_status(book.copies[1].id, CopyStatus.MAINTENANCE)
    factory.lend(factory.member(), book, 0)
    waiting = factory.member()
    reservation = factory.reserve(waiting, book)

    copy = factory.catalog.change_copy_status(book.copies[1].id, CopyStatus.AVAILABLE)

    session.refresh(reservation)
    assert copy.status == CopyStatus.ON_HOLD
    assert reservation.status == ReservationStatus.READY
