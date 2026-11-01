from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ActorDep, ClockDep, PageDep, StaffDep, provide
from app.application.services.fine_service import FineService
from app.application.services.loan_service import LoanService
from app.application.services.reservation_service import ReservationService
from app.domain.enums import FineStatus, LoanStatus, ReservationStatus
from app.schemas.circulation import (
    ExpireHoldsOut,
    FineOut,
    LoanCreate,
    LoanOut,
    ReservationCreate,
    ReservationOut,
    ReturnOut,
)
from app.schemas.common import PageOut

LoanDep = Annotated[LoanService, Depends(provide(LoanService))]
ReservationDep = Annotated[ReservationService, Depends(provide(ReservationService))]
FineDep = Annotated[FineService, Depends(provide(FineService))]

loans = APIRouter(prefix="/loans", tags=["Préstamos"])
reservations = APIRouter(prefix="/reservations", tags=["Reservas"])
fines = APIRouter(prefix="/fines", tags=["Multas"])


# ---- Préstamos -----------------------------------------------------------------------------
@loans.get(
    "",
    response_model=PageOut[LoanOut],
    summary="Listar préstamos (el socio solo ve los suyos)",
)
def list_loans(
    actor: ActorDep,
    service: LoanDep,
    clock: ClockDep,
    params: PageDep,
    member_id: int | None = None,
    status_: Annotated[LoanStatus | None, Query(alias="status")] = None,
    overdue: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> PageOut[LoanOut]:
    page = service.list(
        params, actor=actor, member_id=member_id, status=status_, overdue=overdue, q=q
    )
    today = clock.today()
    return PageOut.build(page, [LoanOut.from_entity(loan, today) for loan in page.items])


@loans.post(
    "",
    response_model=LoanOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar préstamo por carnet y código de inventario",
)
def create_loan(data: LoanCreate, _: StaffDep, service: LoanDep, clock: ClockDep) -> LoanOut:
    loan = service.checkout(card_number=data.card_number, inventory_code=data.inventory_code)
    return LoanOut.from_entity(loan, clock.today())


@loans.get("/{loan_id}", response_model=LoanOut, summary="Detalle de préstamo")
def get_loan(loan_id: int, actor: ActorDep, service: LoanDep, clock: ClockDep) -> LoanOut:
    return LoanOut.from_entity(service.get(loan_id, actor), clock.today())


@loans.post(
    "/{loan_id}/return",
    response_model=ReturnOut,
    summary="Registrar devolución (genera multa y atiende la cola de reservas)",
)
def return_loan(loan_id: int, _: StaffDep, service: LoanDep, clock: ClockDep) -> ReturnOut:
    result = service.return_loan(loan_id)
    reserved = result.reserved_for
    return ReturnOut(
        loan=LoanOut.from_entity(result.loan, clock.today()),
        fine=FineOut.from_entity(result.fine) if result.fine else None,
        reserved_for=ReservationOut.from_entity(reserved, None) if reserved else None,
    )


@loans.post("/{loan_id}/renew", response_model=LoanOut, summary="Renovar préstamo")
def renew_loan(loan_id: int, actor: ActorDep, service: LoanDep, clock: ClockDep) -> LoanOut:
    return LoanOut.from_entity(service.renew(loan_id, actor), clock.today())


# ---- Reservas ------------------------------------------------------------------------------
@reservations.get("", response_model=PageOut[ReservationOut], summary="Listar reservas")
def list_reservations(
    actor: ActorDep,
    service: ReservationDep,
    params: PageDep,
    member_id: int | None = None,
    book_id: int | None = None,
    status_: Annotated[ReservationStatus | None, Query(alias="status")] = None,
) -> PageOut[ReservationOut]:
    page = service.list(params, actor=actor, member_id=member_id, book_id=book_id, status=status_)
    items = [ReservationOut.from_entity(r, service.queue_position(r)) for r in page.items]
    return PageOut.build(page, items)


@reservations.post(
    "",
    response_model=ReservationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar un libro sin ejemplares disponibles (entra a la cola FIFO)",
)
def create_reservation(
    data: ReservationCreate, actor: ActorDep, service: ReservationDep
) -> ReservationOut:
    reservation = service.create(book_id=data.book_id, member_id=data.member_id, actor=actor)
    return ReservationOut.from_entity(reservation, service.queue_position(reservation))


@reservations.post(
    "/expire-holds",
    response_model=ExpireHoldsOut,
    summary="Expirar apartados no recogidos (job de mantenimiento)",
)
def expire_holds(_: StaffDep, service: ReservationDep) -> ExpireHoldsOut:
    return ExpireHoldsOut(expired=service.expire_holds())


@reservations.post("/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_reservation(
    reservation_id: int, actor: ActorDep, service: ReservationDep
) -> ReservationOut:
    reservation = service.cancel(reservation_id, actor)
    return ReservationOut.from_entity(reservation, None)


# ---- Multas --------------------------------------------------------------------------------
@fines.get("", response_model=PageOut[FineOut], summary="Listar multas")
def list_fines(
    actor: ActorDep,
    service: FineDep,
    params: PageDep,
    member_id: int | None = None,
    status_: Annotated[FineStatus | None, Query(alias="status")] = None,
) -> PageOut[FineOut]:
    page = service.list(params, actor=actor, member_id=member_id, status=status_)
    return PageOut.build(page, [FineOut.from_entity(f) for f in page.items])


@fines.post("/{fine_id}/pay", response_model=FineOut, summary="Registrar pago de multa")
def pay_fine(fine_id: int, _: StaffDep, service: FineDep) -> FineOut:
    return FineOut.from_entity(service.pay(fine_id))
