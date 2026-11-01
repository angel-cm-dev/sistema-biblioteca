from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.application.pagination import Page, PageParams
from app.domain.enums import CopyStatus
from app.infrastructure.models import Author, Book, Category, Copy, book_authors
from app.infrastructure.repositories.base import apply_sort, paginate


class CatalogRepository:
    BOOK_SORTABLE = {
        "title": Book.title,
        "isbn": Book.isbn,
        "publication_year": Book.publication_year,
        "created_at": Book.created_at,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- Libros -------------------------------------------------------------------------
    def _book_query(self):
        # selectinload evita el problema N+1 al serializar autores, categoría y ejemplares.
        return select(Book).options(
            selectinload(Book.authors), selectinload(Book.category), selectinload(Book.copies)
        )

    def get_book(self, book_id: int) -> Book | None:
        return self.session.scalar(self._book_query().where(Book.id == book_id))

    def get_book_by_isbn(self, isbn: str) -> Book | None:
        return self.session.scalar(select(Book).where(Book.isbn == isbn))

    def list_books(
        self,
        params: PageParams,
        *,
        q: str | None,
        category_id: int | None,
        author_id: int | None,
        available: bool | None,
    ) -> Page[Book]:
        stmt = self._book_query()
        if q:
            like = f"%{q}%"
            author_match = exists().where(
                book_authors.c.book_id == Book.id,
                book_authors.c.author_id == Author.id,
                Author.name.ilike(like),
            )
            stmt = stmt.where(or_(Book.title.ilike(like), Book.isbn.ilike(like), author_match))
        if category_id:
            stmt = stmt.where(Book.category_id == category_id)
        if author_id:
            stmt = stmt.where(Book.authors.any(Author.id == author_id))
        if available is not None:
            has_available = Book.copies.any(Copy.status == CopyStatus.AVAILABLE)
            stmt = stmt.where(has_available if available else ~has_available)
        stmt = apply_sort(stmt, params.sort, self.BOOK_SORTABLE, Book.id)
        return paginate(self.session, stmt, params)

    def add(self, entity):
        self.session.add(entity)
        self.session.flush()
        return entity

    # ---- Ejemplares ---------------------------------------------------------------------
    def get_copy(self, copy_id: int) -> Copy | None:
        return self.session.get(Copy, copy_id)

    def get_copy_by_code(self, code: str) -> Copy | None:
        return self.session.scalar(
            select(Copy)
            .options(selectinload(Copy.book))
            .where(Copy.inventory_code == code.strip().upper())
        )

    def count_available_copies(self, book_id: int) -> int:
        return (
            self.session.scalar(
                select(func.count(Copy.id)).where(
                    Copy.book_id == book_id, Copy.status == CopyStatus.AVAILABLE
                )
            )
            or 0
        )

    # ---- Autores y categorías -----------------------------------------------------------
    def list_authors(self, q: str | None = None) -> list[Author]:
        stmt = select(Author).order_by(Author.name)
        if q:
            stmt = stmt.where(Author.name.ilike(f"%{q}%"))
        return list(self.session.scalars(stmt))

    def get_authors(self, ids: list[int]) -> list[Author]:
        return list(self.session.scalars(select(Author).where(Author.id.in_(ids))))

    def get_author_by_name(self, name: str) -> Author | None:
        return self.session.scalar(select(Author).where(Author.name.ilike(name)))

    def list_categories(self) -> list[Category]:
        return list(self.session.scalars(select(Category).order_by(Category.name)))

    def get_category(self, category_id: int) -> Category | None:
        return self.session.get(Category, category_id)

    def get_category_by_name(self, name: str) -> Category | None:
        return self.session.scalar(select(Category).where(Category.name.ilike(name)))
