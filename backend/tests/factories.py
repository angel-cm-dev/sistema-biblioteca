"""Constructores de datos de prueba usando los servicios reales."""

import itertools

from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.services.catalog_service import CatalogService
from app.application.services.loan_service import LoanService
from app.application.services.member_service import MemberService
from app.application.services.reservation_service import ReservationService
from app.core.config import Settings
from app.core.security import hash_password
from app.domain.clock import FixedClock
from app.domain.enums import MemberType, Role
from app.infrastructure.models import Book, Member, User
from app.schemas.catalog import AuthorCreate, BookCreate, CategoryCreate
from app.schemas.members import MemberCreate
from app.seed import isbn13

PASSWORD = "Prueba123"
STAFF = Actor(user_id=0, role=Role.LIBRARIAN)


class Factory:
    def __init__(self, session: Session, settings: Settings, clock: FixedClock) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self._seq = itertools.count(1)
        self.catalog = CatalogService(session, settings, clock)
        self.members = MemberService(session, settings, clock)
        self.loans = LoanService(session, settings, clock)
        self.reservations = ReservationService(session, settings, clock)
        self._author_id: int | None = None
        self._category_id: int | None = None

    def book(self, copies: int = 1, title: str | None = None) -> Book:
        n = next(self._seq)
        if self._author_id is None:
            self._author_id = self.catalog.create_author(AuthorCreate(name="Autor Prueba")).id
            self._category_id = self.catalog.create_category(CategoryCreate(name="General")).id
        return self.catalog.create_book(
            BookCreate(
                isbn=isbn13(900 + n),
                title=title or f"Libro {n}",
                author_ids=[self._author_id],
                category_id=self._category_id,
                initial_copies=copies,
            )
        )

    def member(
        self, member_type: MemberType = MemberType.STUDENT, *, password: str | None = None
    ) -> Member:
        n = next(self._seq)
        return self.members.create(
            MemberCreate(
                full_name=f"Socio Prueba {n}",
                email=f"socio{n}@test.pe",
                document_id=f"{40000000 + n}",
                member_type=member_type,
                password=password,
            )
        )

    def staff_user(self, role: Role = Role.LIBRARIAN, email: str | None = None) -> User:
        user = User(
            email=email or f"staff{next(self._seq)}@test.pe",
            full_name="Personal Prueba",
            password_hash=hash_password(PASSWORD, 4),
            role=role,
            is_active=True,
            created_at=self.clock.now(),
        )
        self.session.add(user)
        self.session.commit()
        return user

    def lend(self, member: Member, book: Book, copy_index: int = 0):
        self.session.refresh(book)
        return self.loans.checkout(
            card_number=member.card_number,
            inventory_code=book.copies[copy_index].inventory_code,
        )

    def reserve(self, member: Member, book: Book):
        return self.reservations.create(book_id=book.id, member_id=member.id, actor=STAFF)
