from sqlalchemy.orm import Session

from app.application.pagination import Page, PageParams
from app.application.services.reservation_service import ReservationService
from app.core.config import Settings
from app.domain.clock import Clock
from app.domain.enums import CopyStatus
from app.domain.errors import ConflictError, NotFoundError
from app.infrastructure.models import Author, Book, Category, Copy
from app.infrastructure.repositories.catalog import CatalogRepository
from app.schemas.catalog import (
    AuthorCreate,
    BookCreate,
    BookUpdate,
    CategoryCreate,
    CopyCreate,
)


class CatalogService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.repo = CatalogRepository(session)
        self.reservations = ReservationService(session, settings, clock)

    # ---- Autores / categorías -----------------------------------------------------------
    def list_authors(self, q: str | None) -> list[Author]:
        return self.repo.list_authors(q)

    def create_author(self, data: AuthorCreate) -> Author:
        if self.repo.get_author_by_name(data.name):
            raise ConflictError("Ya existe un autor con ese nombre")
        author = self.repo.add(Author(**data.model_dump()))
        self.session.commit()
        return author

    def list_categories(self) -> list[Category]:
        return self.repo.list_categories()

    def create_category(self, data: CategoryCreate) -> Category:
        if self.repo.get_category_by_name(data.name):
            raise ConflictError("Ya existe una categoría con ese nombre")
        category = self.repo.add(Category(**data.model_dump()))
        self.session.commit()
        return category

    # ---- Libros -------------------------------------------------------------------------
    def list_books(self, params: PageParams, **filters) -> Page[Book]:
        return self.repo.list_books(params, **filters)

    def get_book(self, book_id: int) -> Book:
        book = self.repo.get_book(book_id)
        if not book:
            raise NotFoundError("Libro no encontrado")
        return book

    def queue_length(self, book_id: int) -> int:
        return len(self.reservations.repo.queue_for_book(book_id))

    def _resolve_relations(self, author_ids: list[int] | None, category_id: int | None):
        authors = None
        if author_ids is not None:
            unique_ids = sorted(set(author_ids))
            authors = self.repo.get_authors(unique_ids)
            if len(authors) != len(unique_ids):
                missing = set(unique_ids) - {a.id for a in authors}
                raise NotFoundError(f"Autores no encontrados: {sorted(missing)}")
        if category_id is not None and not self.repo.get_category(category_id):
            raise NotFoundError("Categoría no encontrada")
        return authors

    def create_book(self, data: BookCreate) -> Book:
        if self.repo.get_book_by_isbn(data.isbn):
            raise ConflictError("Ya existe un libro con ese ISBN", code="isbn_taken")
        authors = self._resolve_relations(data.author_ids, data.category_id)
        book = Book(
            isbn=data.isbn,
            title=data.title.strip(),
            publisher=data.publisher,
            publication_year=data.publication_year,
            category_id=data.category_id,
            authors=authors or [],
            created_at=self.clock.now(),
        )
        self.repo.add(book)
        for _ in range(data.initial_copies):
            self._new_copy(book, CopyCreate())
        self.session.commit()
        return self.get_book(book.id)

    def update_book(self, book_id: int, data: BookUpdate) -> Book:
        book = self.get_book(book_id)
        changes = data.model_dump(exclude_unset=True)
        authors = self._resolve_relations(
            changes.pop("author_ids", None), changes.get("category_id")
        )
        if authors is not None:
            book.authors = authors
        for field, value in changes.items():
            setattr(book, field, value)
        self.session.commit()
        return self.get_book(book.id)

    # ---- Ejemplares ---------------------------------------------------------------------
    def _new_copy(self, book: Book, data: CopyCreate) -> Copy:
        if data.inventory_code:
            code = data.inventory_code.upper()
            if self.repo.get_copy_by_code(code):
                raise ConflictError("El código de inventario ya existe", code="inventory_taken")
        else:
            # Código autogenerado: INV-<id libro>-<correlativo del ejemplar>
            code = f"INV-{book.id:05d}-{len(book.copies) + 1:03d}"
            while self.repo.get_copy_by_code(code):
                code = f"{code}X"
        copy = Copy(
            book=book,
            inventory_code=code,
            status=CopyStatus.AVAILABLE,
            location=data.location,
            created_at=self.clock.now(),
        )
        self.repo.add(copy)
        return copy

    def add_copy(self, book_id: int, data: CopyCreate) -> Copy:
        book = self.get_book(book_id)
        copy = self._new_copy(book, data)
        # Un ejemplar nuevo puede atender de inmediato al primero de la cola de reservas.
        self.reservations.route_copy(copy)
        self.session.commit()
        return copy

    def change_copy_status(self, copy_id: int, status: CopyStatus) -> Copy:
        copy = self.repo.get_copy(copy_id)
        if not copy:
            raise NotFoundError("Ejemplar no encontrado")
        if copy.status in (CopyStatus.LOANED, CopyStatus.ON_HOLD):
            raise ConflictError(
                f"El ejemplar está '{copy.status}'; registre la devolución o cancele la reserva",
                code="copy_in_circulation",
            )
        if status == CopyStatus.AVAILABLE:
            # Vuelve a circular: si hay cola, queda apartado para el primero (no "disponible").
            self.reservations.route_copy(copy)
        else:
            copy.status = status
        self.session.commit()
        return copy
