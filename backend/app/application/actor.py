"""Quién ejecuta una operación. Los servicios reciben un `Actor` en lugar del request HTTP."""

from dataclasses import dataclass

from app.domain.enums import Role
from app.domain.errors import PermissionDeniedError


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: int
    role: Role
    member_id: int | None = None

    @property
    def is_staff(self) -> bool:
        return self.role in (Role.ADMIN, Role.LIBRARIAN)

    def scope_member_id(self) -> int | None:
        """Para listados: un socio solo ve lo suyo; el personal ve todo (None = sin filtro)."""
        if self.is_staff:
            return None
        if self.member_id is None:
            raise PermissionDeniedError("Su cuenta no está vinculada a un socio")
        return self.member_id

    def ensure_owns(self, member_id: int) -> None:
        if not self.is_staff and self.member_id != member_id:
            raise PermissionDeniedError("Solo puede gestionar sus propios registros")
