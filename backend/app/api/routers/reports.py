from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import StaffDep, provide
from app.application.services.report_service import ReportService
from app.domain.errors import DomainError
from app.schemas.common import cents_to_decimal
from app.schemas.reports import DelinquencyOut, DelinquentMember, SummaryOut, TopBookOut

router = APIRouter(prefix="/reports", tags=["Reportes"])
ReportDep = Annotated[ReportService, Depends(provide(ReportService))]


@router.get("/summary", response_model=SummaryOut, summary="KPIs para el dashboard")
def summary(_: StaffDep, service: ReportDep) -> SummaryOut:
    data = service.summary()
    cents = data.pop("pending_fines_cents")
    return SummaryOut(**data, pending_fines=cents_to_decimal(cents))


@router.get("/most-borrowed", response_model=list[TopBookOut], summary="Libros más prestados")
def most_borrowed(
    _: StaffDep,
    service: ReportDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[TopBookOut]:
    if date_from and date_to and date_from > date_to:
        raise DomainError("date_from no puede ser posterior a date_to", code="invalid_range")
    rows = service.most_borrowed(limit=limit, date_from=date_from, date_to=date_to)
    return [
        TopBookOut(book_id=book_id, title=title, isbn=isbn, loans=count)
        for book_id, title, isbn, count in rows
    ]


@router.get("/delinquency", response_model=list[DelinquencyOut], summary="Reporte de morosidad")
def delinquency(_: StaffDep, service: ReportDep) -> list[DelinquencyOut]:
    return [
        DelinquencyOut(
            member=DelinquentMember.model_validate(row["member"]),
            pending_debt=cents_to_decimal(row["pending_debt_cents"]),
            overdue_loans=row["overdue_loans"],
            max_days_overdue=row["max_days_overdue"],
            is_blocked=row["is_blocked"],
        )
        for row in service.delinquency()
    ]
