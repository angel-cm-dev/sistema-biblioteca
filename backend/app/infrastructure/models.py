"""Modelos ORM (tablas).

Decisión: las entidades persistentes se modelan una sola vez con SQLAlchemy y las reglas de
negocio puras viven en `app.domain.policies`. Duplicar entidades de dominio + mapeadores sería
ceremonia sin beneficio en un sistema de este tamaño (ver docs/decisiones/0001).
"""

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    TypeDecorator,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    CopyStatus,
    FineStatus,
    LoanStatus,
    MemberType,
    ReservationStatus,
    Role,
)
from app.infrastructure.database import Base


class UTCDateTime(TypeDecorator):
    """Guarda fechas en UTC sin zona y las devuelve con tzinfo=UTC.

    SQLite no tiene tipo con zona horaria; sin esto, compararíamos datetimes "naive" con
    "aware" y Python lanzaría TypeError. En PostgreSQL funciona igual de bien.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def str_enum(enum_cls: type[StrEnum]) -> Enum:
    """Enum guardado como VARCHAR con su valor legible (portable entre SQLite y PostgreSQL)."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(str_enum(Role))
    is_active: Mapped[bool] = mapped_column(default=True)
    member_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    member: Mapped["Member | None"] = relationship(back_populates="user")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    document_id: Mapped[str] = mapped_column(String(15), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    member_type: Mapped[MemberType] = mapped_column(str_enum(MemberType))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    user: Mapped[User | None] = relationship(back_populates="member")
    loans: Mapped[list["Loan"]] = relationship(back_populates="member")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    nationality: Mapped[str | None] = mapped_column(String(60))

    books: Mapped[list["Book"]] = relationship(secondary=book_authors, back_populates="authors")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    books: Mapped[list["Book"]] = relationship(back_populates="category")


class Book(Base):
    """Obra bibliográfica (el "título"). Los objetos físicos que se prestan son `Copy`."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(String(17), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    publisher: Mapped[str | None] = mapped_column(String(120))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    category: Mapped[Category | None] = relationship(back_populates="books")
    authors: Mapped[list[Author]] = relationship(secondary=book_authors, back_populates="books")
    copies: Mapped[list["Copy"]] = relationship(
        back_populates="book", cascade="all, delete-orphan", order_by="Copy.inventory_code"
    )


class Copy(Base):
    """Ejemplar físico con código de inventario único (el que lleva el código de barras)."""

    __tablename__ = "copies"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    inventory_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[CopyStatus] = mapped_column(str_enum(CopyStatus), default=CopyStatus.AVAILABLE)
    location: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    book: Mapped[Book] = relationship(back_populates="copies")


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (Index("ix_loans_member_status", "member_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    copy_id: Mapped[int] = mapped_column(ForeignKey("copies.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    loaned_at: Mapped[datetime] = mapped_column(UTCDateTime)
    due_date: Mapped[date] = mapped_column(Date)
    returned_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    renewals_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[LoanStatus] = mapped_column(str_enum(LoanStatus), default=LoanStatus.ACTIVE)

    copy: Mapped[Copy] = relationship()
    member: Mapped[Member] = relationship(back_populates="loans")


class Reservation(Base):
    """Reserva de un libro (no de un ejemplar). La cola FIFO se ordena por created_at, id."""

    __tablename__ = "reservations"
    __table_args__ = (Index("ix_reservations_book_status", "book_id", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        str_enum(ReservationStatus), default=ReservationStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    copy_id: Mapped[int | None] = mapped_column(ForeignKey("copies.id"))
    ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    book: Mapped[Book] = relationship()
    member: Mapped[Member] = relationship()
    copy: Mapped[Copy | None] = relationship()


class Fine(Base):
    __tablename__ = "fines"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id"), unique=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    days_late: Mapped[int]
    amount_cents: Mapped[int]
    status: Mapped[FineStatus] = mapped_column(str_enum(FineStatus), default=FineStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    loan: Mapped[Loan] = relationship()
    member: Mapped[Member] = relationship()
