"""Dependencias de FastAPI: sesión de BD, reloj, usuario actual y control de roles.

Todo lo que un endpoint necesita llega por `Depends`, así las pruebas pueden reemplazar
cualquier pieza con `app.dependency_overrides` (p.ej. el reloj o la base de datos).
"""

from collections.abc import Callable, Iterator
from typing import Annotated

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.pagination import PageParams
from app.core.config import Settings
from app.core.security import decode_access_token
from app.domain.clock import Clock
from app.domain.enums import Role
from app.domain.errors import AuthenticationError, PermissionDeniedError
from app.infrastructure.database import session_scope
from app.infrastructure.models import User

bearer_scheme = HTTPBearer(auto_error=False, description="Token JWT obtenido en /auth/login")


def get_db(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


SessionDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
ClockDep = Annotated[Clock, Depends(get_clock)]


def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise AuthenticationError("Falta el token de acceso (Authorization: Bearer <token>)")
    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("El token expiró", code="token_expired") from exc
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AuthenticationError("Token inválido", code="invalid_token") from exc
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise AuthenticationError("Usuario no válido o desactivado")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def provide[S](service_cls: Callable[[Session, Settings, Clock], S]) -> Callable[..., S]:
    """Fábrica de dependencias: construye un servicio con sesión, configuración y reloj."""

    def factory(session: SessionDep, settings: SettingsDep, clock: ClockDep) -> S:
        return service_cls(session, settings, clock)

    return factory


def get_actor(user: CurrentUser) -> Actor:
    return Actor(user_id=user.id, role=user.role, member_id=user.member_id)


def require_roles(*roles: Role) -> Callable[[Actor], Actor]:
    """Autorización declarativa por endpoint: `Depends(require_roles(Role.ADMIN))`."""

    def checker(actor: Annotated[Actor, Depends(get_actor)]) -> Actor:
        if actor.role not in roles:
            raise PermissionDeniedError("No tiene permisos para esta operación")
        return actor

    return checker


ActorDep = Annotated[Actor, Depends(get_actor)]
StaffDep = Annotated[Actor, Depends(require_roles(Role.ADMIN, Role.LIBRARIAN))]
AdminDep = Annotated[Actor, Depends(require_roles(Role.ADMIN))]


def page_params(
    page: Annotated[int, Query(ge=1, description="Página (desde 1)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Tamaño de página")] = 20,
    sort: Annotated[
        str | None,
        Query(pattern=r"^-?[a-z_]+$", description="Campo de orden; prefijo '-' = descendente"),
    ] = None,
) -> PageParams:
    return PageParams(page=page, size=size, sort=sort)


PageDep = Annotated[PageParams, Depends(page_params)]
