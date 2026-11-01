from sqlalchemy.orm import Session

from app.application.pagination import Page, PageParams
from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.clock import Clock
from app.domain.enums import Role
from app.domain.errors import AuthenticationError, BusinessRuleError, ConflictError, NotFoundError
from app.infrastructure.models import User
from app.infrastructure.repositories.members import MemberRepository
from app.infrastructure.repositories.users import UserRepository
from app.schemas.auth import UserCreate


class AuthService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self.users = UserRepository(session)
        self.members = MemberRepository(session)

    def authenticate(self, email: str, password: str) -> tuple[str, User]:
        user = self.users.get_by_email(email)
        # Mismo mensaje para "no existe" y "contraseña incorrecta": no revelamos qué correos
        # están registrados (evita enumeración de usuarios).
        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError("Correo o contraseña incorrectos", code="invalid_credentials")
        if not user.is_active:
            raise AuthenticationError("La cuenta está desactivada", code="inactive_user")
        token = create_access_token(subject=str(user.id), role=user.role, settings=self.settings)
        return token, user

    def get_active_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Usuario no válido o desactivado")
        return user

    def create_user(self, data: UserCreate) -> User:
        if self.users.get_by_email(data.email):
            raise ConflictError("Ya existe un usuario con ese correo", code="email_taken")
        if data.role == Role.MEMBER:
            if data.member_id is None:
                raise BusinessRuleError("Un usuario 'socio' debe vincularse a un socio")
            if not self.members.get(data.member_id):
                raise NotFoundError("Socio no encontrado")
        user = User(
            email=data.email.lower(),
            full_name=data.full_name,
            password_hash=hash_password(data.password, self.settings.bcrypt_rounds),
            role=data.role,
            member_id=data.member_id if data.role == Role.MEMBER else None,
            is_active=True,
            created_at=self.clock.now(),
        )
        self.users.add(user)
        self.session.commit()
        return user

    def list_users(self, params: PageParams, q: str | None, role: Role | None) -> Page[User]:
        return self.users.list(params, q=q, role=role)
