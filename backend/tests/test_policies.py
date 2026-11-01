"""Pruebas unitarias de las reglas puras del dominio (sin base de datos)."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain import policies
from app.domain.enums import MemberType
from app.schemas.catalog import normalize_isbn


@pytest.mark.parametrize(
    ("member_type", "max_loans", "days", "renewals"),
    [
        (MemberType.STUDENT, 3, 14, 2),
        (MemberType.TEACHER, 10, 30, 3),
        (MemberType.EXTERNAL, 2, 7, 1),
    ],
)
def test_policy_per_member_type(member_type, max_loans, days, renewals):
    policy = policies.policy_for(member_type)
    assert (policy.max_active_loans, policy.loan_days, policy.max_renewals) == (
        max_loans,
        days,
        renewals,
    )


def test_due_date_depends_on_member_type():
    start = date(2026, 3, 1)
    assert policies.due_date_for(start, MemberType.STUDENT) == date(2026, 3, 15)
    assert policies.due_date_for(start, MemberType.EXTERNAL) == date(2026, 3, 8)


@pytest.mark.parametrize(
    ("returned", "expected"),
    [
        (date(2026, 3, 9), 0),
        (date(2026, 3, 10), 0),
        (date(2026, 3, 11), 1),
        (date(2026, 3, 20), 10),
    ],
)
def test_days_late(returned, expected):
    assert policies.days_late(date(2026, 3, 10), returned) == expected


def test_fine_amount_in_cents():
    assert policies.fine_amount_cents(5, Decimal("1.50")) == 750
    assert policies.fine_amount_cents(0, Decimal("1.00")) == 0


@pytest.mark.parametrize(
    ("debt_cents", "threshold", "blocked"),
    [
        (999, Decimal("10.00"), False),
        (1000, Decimal("10.00"), True),
        (1500, Decimal("10.00"), True),
        (0, Decimal("0"), False),
        (1, Decimal("0"), True),
    ],
)
def test_block_by_debt_threshold(debt_cents, threshold, blocked):
    assert policies.is_blocked_by_debt(debt_cents, threshold) is blocked


def test_renewal_allowed_when_rules_pass():
    assert (
        policies.renewal_rejection_reason(
            member_type=MemberType.STUDENT,
            renewals_done=1,
            is_overdue=False,
            has_pending_reservations=False,
        )
        is None
    )


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"renewals_done": 2}, "máximo"),
        ({"has_pending_reservations": True}, "cola de reserva"),
        ({"is_overdue": True}, "vencido"),
    ],
)
def test_renewal_rejections(kwargs, fragment):
    params = {
        "member_type": MemberType.STUDENT,
        "renewals_done": 0,
        "is_overdue": False,
        "has_pending_reservations": False,
    } | kwargs
    reason = policies.renewal_rejection_reason(**params)
    assert reason is not None and fragment in reason


def test_isbn_validation():
    assert normalize_isbn("978-0-306-40615-7") == "9780306406157"
    assert normalize_isbn("0-306-40615-2") == "0306406152"
    with pytest.raises(ValueError):
        normalize_isbn("978-0-306-40615-8")
    with pytest.raises(ValueError):
        normalize_isbn("12345")
