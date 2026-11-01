from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ActorDep, PageDep, StaffDep, provide
from app.application.services.member_service import MemberService, MemberStanding
from app.domain.enums import MemberType
from app.domain.errors import PermissionDeniedError
from app.schemas.common import PageOut, cents_to_decimal
from app.schemas.members import (
    LoanPolicyOut,
    MemberCreate,
    MemberOut,
    MemberStatusOut,
    MemberUpdate,
)

router = APIRouter(prefix="/members", tags=["Socios"])
MemberServiceDep = Annotated[MemberService, Depends(provide(MemberService))]


def to_status(standing: MemberStanding) -> MemberStatusOut:
    p = standing.policy
    return MemberStatusOut(
        member=MemberOut.model_validate(standing.member),
        policy=LoanPolicyOut(
            max_active_loans=p.max_active_loans, loan_days=p.loan_days, max_renewals=p.max_renewals
        ),
        active_loans=standing.active_loans,
        overdue_loans=standing.overdue_loans,
        pending_debt=cents_to_decimal(standing.pending_debt_cents),
        is_blocked=standing.is_blocked,
        block_reasons=standing.block_reasons,
        can_borrow=standing.can_borrow,
    )


@router.get("", response_model=PageOut[MemberOut], summary="Listar socios")
def list_members(
    _: StaffDep,
    service: MemberServiceDep,
    params: PageDep,
    q: Annotated[
        str | None, Query(max_length=100, description="Nombre, carnet, DNI, correo")
    ] = None,
    member_type: MemberType | None = None,
    is_active: bool | None = None,
) -> PageOut[MemberOut]:
    page = service.list(params, q=q, member_type=member_type, is_active=is_active)
    return PageOut.build(page, [MemberOut.model_validate(m) for m in page.items])


@router.post(
    "", response_model=MemberOut, status_code=status.HTTP_201_CREATED, summary="Registrar socio"
)
def create_member(data: MemberCreate, _: StaffDep, service: MemberServiceDep) -> MemberOut:
    return MemberOut.model_validate(service.create(data))


@router.get("/me/status", response_model=MemberStatusOut, summary="Mi situación (socio)")
def my_status(actor: ActorDep, service: MemberServiceDep) -> MemberStatusOut:
    if actor.member_id is None:
        raise PermissionDeniedError("Su cuenta no está vinculada a un socio")
    return to_status(service.standing(service.get(actor.member_id)))


@router.get("/{member_id}", response_model=MemberOut, summary="Detalle de socio")
def get_member(member_id: int, actor: ActorDep, service: MemberServiceDep) -> MemberOut:
    return MemberOut.model_validate(service.get(member_id, actor))


@router.get(
    "/{member_id}/status",
    response_model=MemberStatusOut,
    summary="Situación del socio: límites, deuda y bloqueos",
)
def member_status(member_id: int, actor: ActorDep, service: MemberServiceDep) -> MemberStatusOut:
    return to_status(service.standing(service.get(member_id, actor)))


@router.patch("/{member_id}", response_model=MemberOut, summary="Actualizar socio")
def update_member(
    member_id: int, data: MemberUpdate, _: StaffDep, service: MemberServiceDep
) -> MemberOut:
    return MemberOut.model_validate(service.update(member_id, data))
