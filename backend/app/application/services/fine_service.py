from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.pagination import Page, PageParams
from app.core.config import Settings
from app.domain.clock import Clock
from app.domain.enums import FineStatus
from app.domain.errors import ConflictError, NotFoundError
from app.infrastructure.models import Fine
from app.infrastructure.repositories.circulation import FineRepository


class FineService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.repo = FineRepository(session)

    def list(
        self,
        params: PageParams,
        *,
        actor: Actor,
        member_id: int | None,
        status: FineStatus | None,
    ) -> Page[Fine]:
        scoped = actor.scope_member_id()
        return self.repo.list(params, member_id=scoped or member_id, status=status)

    def pay(self, fine_id: int) -> Fine:
        """Registra el pago en caja. Al bajar la deuda, el socio puede quedar desbloqueado."""
        fine = self.repo.get(fine_id)
        if not fine:
            raise NotFoundError("Multa no encontrada")
        if fine.status == FineStatus.PAID:
            raise ConflictError("La multa ya fue pagada", code="already_paid")
        fine.status = FineStatus.PAID
        fine.paid_at = self.clock.now()
        self.session.commit()
        return self.repo.get(fine.id)
