from datetime import date

from pydantic import Field, field_validator

from app.domain.enums import CopyStatus
from app.schemas.common import ApiModel


def normalize_isbn(value: str) -> str:
    """Normaliza (quita guiones/espacios) y valida el dígito de control de ISBN-10/13.

    Validar el checksum detecta errores de tipeo al catalogar, que de otro modo crearían
    libros duplicados con ISBN "casi" iguales.
    """
    digits = value.replace("-", "").replace(" ", "").upper()
    if len(digits) == 13 and digits.isdigit():
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
        if (10 - total % 10) % 10 != int(digits[12]):
            raise ValueError("ISBN-13 con dígito de control inválido")
        return digits
    if len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        total = sum((10 - i) * int(d) for i, d in enumerate(digits[:9]))
        check = 10 if digits[9] == "X" else int(digits[9])
        if (total + check) % 11 != 0:
            raise ValueError("ISBN-10 con dígito de control inválido")
        return digits
    raise ValueError("El ISBN debe tener 10 o 13 dígitos")


class AuthorCreate(ApiModel):
    name: str = Field(min_length=2, max_length=120)
    nationality: str | None = Field(default=None, max_length=60)


class AuthorOut(AuthorCreate):
    id: int


class CategoryCreate(ApiModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=255)


class CategoryOut(CategoryCreate):
    id: int


class BookBase(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    publisher: str | None = Field(default=None, max_length=120)
    publication_year: int | None = Field(default=None, ge=1450)
    category_id: int | None = None

    @field_validator("publication_year")
    @classmethod
    def not_in_future(cls, value: int | None) -> int | None:
        if value is not None and value > date.today().year + 1:
            raise ValueError("El año de publicación no puede estar en el futuro")
        return value


class BookCreate(BookBase):
    isbn: str = Field(examples=["978-612-00-0001-3"])
    author_ids: list[int] = Field(min_length=1, description="Al menos un autor")
    initial_copies: int = Field(default=0, ge=0, le=50, description="Ejemplares a crear")

    @field_validator("isbn")
    @classmethod
    def check_isbn(cls, value: str) -> str:
        return normalize_isbn(value)


class BookUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    publisher: str | None = Field(default=None, max_length=120)
    publication_year: int | None = Field(default=None, ge=1450)
    category_id: int | None = None
    author_ids: list[int] | None = Field(default=None, min_length=1)


class CopyCreate(ApiModel):
    inventory_code: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9-]{3,30}$",
        description="Si se omite se genera automáticamente",
    )
    location: str | None = Field(default=None, max_length=60, examples=["Estante A-3"])


class CopyStatusUpdate(ApiModel):
    # 'prestado' y 'apartado' solo los asigna el sistema (préstamos y reservas), nunca a mano.
    status: CopyStatus

    @field_validator("status")
    @classmethod
    def only_manual_states(cls, value: CopyStatus) -> CopyStatus:
        allowed = {CopyStatus.AVAILABLE, CopyStatus.MAINTENANCE, CopyStatus.LOST}
        if value not in allowed:
            raise ValueError("Solo se puede asignar: disponible, mantenimiento o perdido")
        return value


class CopyOut(ApiModel):
    id: int
    book_id: int
    inventory_code: str
    status: CopyStatus
    location: str | None


class BookOut(ApiModel):
    id: int
    isbn: str
    title: str
    publisher: str | None
    publication_year: int | None
    category: CategoryOut | None
    authors: list[AuthorOut]
    total_copies: int
    available_copies: int

    @classmethod
    def from_entity(cls, book) -> "BookOut":
        return cls(
            id=book.id,
            isbn=book.isbn,
            title=book.title,
            publisher=book.publisher,
            publication_year=book.publication_year,
            category=CategoryOut.model_validate(book.category) if book.category else None,
            authors=[AuthorOut.model_validate(a) for a in book.authors],
            total_copies=len(book.copies),
            available_copies=sum(1 for c in book.copies if c.status == CopyStatus.AVAILABLE),
        )


class BookDetailOut(BookOut):
    copies: list[CopyOut]
    queue_length: int = 0

    @classmethod
    def from_entity_detail(cls, book, queue_length: int) -> "BookDetailOut":
        base = BookOut.from_entity(book).model_dump()
        return cls(
            **base,
            copies=[CopyOut.model_validate(c) for c in book.copies],
            queue_length=queue_length,
        )
