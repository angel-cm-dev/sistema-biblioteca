from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AdminDep, CurrentUser, PageDep, SettingsDep, provide
from app.application.services.auth_service import AuthService
from app.domain.enums import Role
from app.schemas.auth import LoginIn, TokenOut, UserCreate, UserOut
from app.schemas.common import PageOut

router = APIRouter(tags=["Autenticación y usuarios"])
AuthServiceDep = Annotated[AuthService, Depends(provide(AuthService))]


@router.post("/auth/login", response_model=TokenOut, summary="Iniciar sesión y obtener JWT")
def login(data: LoginIn, service: AuthServiceDep, settings: SettingsDep) -> TokenOut:
    token, user = service.authenticate(data.email, data.password)
    return TokenOut(
        access_token=token,
        expires_in=settings.jwt_expires_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/auth/me", response_model=UserOut, summary="Usuario autenticado")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/users", response_model=PageOut[UserOut], summary="Listar usuarios (admin)")
def list_users(
    _: AdminDep,
    service: AuthServiceDep,
    params: PageDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: Role | None = None,
) -> PageOut[UserOut]:
    page = service.list_users(params, q, role)
    return PageOut.build(page, [UserOut.model_validate(u) for u in page.items])


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario (admin)",
)
def create_user(data: UserCreate, _: AdminDep, service: AuthServiceDep) -> UserOut:
    return UserOut.model_validate(service.create_user(data))
