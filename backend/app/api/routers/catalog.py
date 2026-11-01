from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ActorDep, PageDep, StaffDep, provide
from app.application.services.catalog_service import CatalogService
from app.schemas.catalog import (
    AuthorCreate,
    AuthorOut,
    BookCreate,
    BookDetailOut,
    BookOut,
    BookUpdate,
    CategoryCreate,
    CategoryOut,
    CopyCreate,
    CopyOut,
    CopyStatusUpdate,
)
from app.schemas.common import PageOut

router = APIRouter(tags=["Catálogo"])
CatalogDep = Annotated[CatalogService, Depends(provide(CatalogService))]


# ---- Autores -------------------------------------------------------------------------------
@router.get("/authors", response_model=list[AuthorOut], summary="Listar autores")
def list_authors(
    _: ActorDep, service: CatalogDep, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[AuthorOut]:
    return [AuthorOut.model_validate(a) for a in service.list_authors(q)]


@router.post("/authors", response_model=AuthorOut, status_code=status.HTTP_201_CREATED)
def create_author(data: AuthorCreate, _: StaffDep, service: CatalogDep) -> AuthorOut:
    return AuthorOut.model_validate(service.create_author(data))


# ---- Categorías ----------------------------------------------------------------------------
@router.get("/categories", response_model=list[CategoryOut], summary="Listar categorías")
def list_categories(_: ActorDep, service: CatalogDep) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in service.list_categories()]


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, _: StaffDep, service: CatalogDep) -> CategoryOut:
    return CategoryOut.model_validate(service.create_category(data))


# ---- Libros --------------------------------------------------------------------------------
@router.get("/books", response_model=PageOut[BookOut], summary="Buscar en el catálogo")
def list_books(
    _: ActorDep,
    service: CatalogDep,
    params: PageDep,
    q: Annotated[str | None, Query(max_length=100, description="Título, ISBN o autor")] = None,
    category_id: int | None = None,
    author_id: int | None = None,
    available: Annotated[
        bool | None, Query(description="true = con ejemplares disponibles")
    ] = None,
) -> PageOut[BookOut]:
    page = service.list_books(
        params, q=q, category_id=category_id, author_id=author_id, available=available
    )
    return PageOut.build(page, [BookOut.from_entity(b) for b in page.items])


@router.post(
    "/books",
    response_model=BookDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar libro (opcionalmente con ejemplares)",
)
def create_book(data: BookCreate, _: StaffDep, service: CatalogDep) -> BookDetailOut:
    book = service.create_book(data)
    return BookDetailOut.from_entity_detail(book, queue_length=0)


@router.get("/books/{book_id}", response_model=BookDetailOut, summary="Detalle con ejemplares")
def get_book(book_id: int, _: ActorDep, service: CatalogDep) -> BookDetailOut:
    book = service.get_book(book_id)
    return BookDetailOut.from_entity_detail(book, service.queue_length(book.id))


@router.patch("/books/{book_id}", response_model=BookDetailOut, summary="Actualizar libro")
def update_book(book_id: int, data: BookUpdate, _: StaffDep, service: CatalogDep) -> BookDetailOut:
    book = service.update_book(book_id, data)
    return BookDetailOut.from_entity_detail(book, service.queue_length(book.id))


# ---- Ejemplares ----------------------------------------------------------------------------
@router.post(
    "/books/{book_id}/copies",
    response_model=CopyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar ejemplar físico",
)
def add_copy(book_id: int, data: CopyCreate, _: StaffDep, service: CatalogDep) -> CopyOut:
    return CopyOut.model_validate(service.add_copy(book_id, data))


@router.patch(
    "/copies/{copy_id}/status",
    response_model=CopyOut,
    summary="Cambiar estado de un ejemplar (disponible, mantenimiento, perdido)",
)
def change_copy_status(
    copy_id: int, data: CopyStatusUpdate, _: StaffDep, service: CatalogDep
) -> CopyOut:
    return CopyOut.model_validate(service.change_copy_status(copy_id, data.status))
