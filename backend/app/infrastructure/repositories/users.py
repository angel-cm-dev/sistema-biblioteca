from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.application.pagination import Page, PageParams
from app.domain.enums import Role
from app.infrastructure.models import User
from app.infrastructure.repositories.base import apply_sort, paginate


class UserRepository:
    SORTABLE = {"email": User.email, "full_name": User.full_name, "role": User.role}

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email.lower()))

    def list(self, params: PageParams, *, q: str | None, role: Role | None) -> Page[User]:
        stmt = select(User)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
        if role:
            stmt = stmt.where(User.role == role)
        stmt = apply_sort(stmt, params.sort, self.SORTABLE, User.id)
        return paginate(self.session, stmt, params)

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user
