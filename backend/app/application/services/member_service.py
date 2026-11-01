from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.pagination import Page, PageParams
from app.core.config import Settings
from app.core.security import hash_password
from app.domain import policies
from app.domain.clock import Clock
from app.domain.enums import MemberType, Role
from app.domain.errors import ConflictError, NotFoundError
from app.infrastructure.models import Member, User
from app.infrastructure.repositories.circulation import FineRepository, LoanRepository
from app.infrastructure.repositories.members import MemberRepository
from app.infrastructure.repositories.users import UserRepository
from app.schemas.members import MemberCreate, MemberUpdate


@dataclass(slots=True)
class MemberStanding:
    """Situación de un socio frente a las reglas de préstamo."""

    member: Member
    policy: policies.LoanPolicy
    active_loans: int
    overdue_loans: int
    pending_debt_cents: int
    is_blocked: bool
    block_reasons: list[str]

    @property
    def can_borrow(self) -> bool:
        return not self.block_reasons and self.active_loans < self.policy.max_active_loans


class MemberService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self.members = MemberRepository(session)
        self.users = UserRepository(session)
        self.loans = LoanRepository(session)
        self.fines = FineRepository(session)

    def get(self, member_id: int, actor: Actor | None = None) -> Member:
        member = self.members.get(member_id)
        if not member:
            raise NotFoundError("Socio no encontrado")
        if actor:
            actor.ensure_owns(member.id)
        return member

    def list(
        self,
        params: PageParams,
        *,
        q: str | None,
        member_type: MemberType | None,
        is_active: bool | None,
    ) -> Page[Member]:
        return self.members.list(params, q=q, member_type=member_type, is_active=is_active)

    def _generate_card_number(self) -> str:
        # Carnet legible: BIB-<año>-<correlativo>. El correlativo usa el máximo id + 1; en un
        # escenario de alta concurrencia se usaría una secuencia de base de datos.
        seq = self.members.next_card_sequence()
        return f"BIB-{self.clock.today().year}-{seq:04d}"

    def create(self, data: MemberCreate) -> Member:
        email = data.email.lower()
        duplicated = self.members.exists_with(email=email, document_id=data.document_id)
        if duplicated:
            label = "correo" if duplicated == "email" else "documento"
            raise ConflictError(f"Ya existe un socio con ese {label}", code=f"{duplicated}_taken")
        if data.password and self.users.get_by_email(email):
            raise ConflictError(
                "Ya existe una cuenta de usuario con ese correo", code="email_taken"
            )

        member = Member(
            card_number=self._generate_card_number(),
            full_name=data.full_name,
            email=email,
            document_id=data.document_id,
            phone=data.phone,
            member_type=data.member_type,
            is_active=True,
            created_at=self.clock.now(),
        )
        self.members.add(member)
        if data.password:
            self.users.add(
                User(
                    email=email,
                    full_name=data.full_name,
                    password_hash=hash_password(data.password, self.settings.bcrypt_rounds),
                    role=Role.MEMBER,
                    member_id=member.id,
                    is_active=True,
                    created_at=self.clock.now(),
                )
            )
        self.session.commit()
        return member

    def update(self, member_id: int, data: MemberUpdate) -> Member:
        member = self.get(member_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("email"):
            changes["email"] = changes["email"].lower()
            if self.members.exists_with(
                email=changes["email"], document_id="__ignore__", exclude_id=member.id
            ):
                raise ConflictError("Ya existe un socio con ese correo", code="email_taken")
        for field, value in changes.items():
            if value is not None:
                setattr(member, field, value)
        self.session.commit()
        return member

    def standing(self, member: Member) -> MemberStanding:
        today = self.clock.today()
        policy = policies.policy_for(member.member_type)
        active = self.loans.count_active(member.id)
        overdue = self.loans.count_overdue(member.id, today)
        debt = self.fines.pending_debt_cents(member.id)
        reasons: list[str] = []
        if not member.is_active:
            reasons.append("El socio está inactivo")
        if policies.is_blocked_by_debt(debt, self.settings.debt_block_threshold):
            threshold = self.settings.debt_block_threshold
            reasons.append(f"Deuda pendiente igual o mayor al umbral de S/ {threshold}")
        if overdue:
            reasons.append("Tiene préstamos vencidos sin devolver")
        return MemberStanding(
            member=member,
            policy=policy,
            active_loans=active,
            overdue_loans=overdue,
            pending_debt_cents=debt,
            is_blocked=bool(reasons),
            block_reasons=reasons,
        )
