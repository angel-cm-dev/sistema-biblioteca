"""Utilidades comunes para repositorios: paginación y ordenamiento seguro."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.application.pagination import Page, PageParams
from app.domain.errors import DomainError


def apply_sort(stmt: Select, sort: str | None, allowed: Mapping[str, Any], default: Any) -> Select:
    """Aplica `?sort=campo` o `?sort=-campo` usando una lista blanca de columnas.

    La lista blanca evita que el cliente ordene por columnas internas o provoque errores SQL.
    """
    if not sort:
        return stmt.order_by(default)
    descending = sort.startswith("-")
    key = sort.lstrip("-+")
    column = allowed.get(key)
    if column is None:
        raise DomainError(
            f"No se puede ordenar por '{key}'. Valores permitidos: {', '.join(sorted(allowed))}",
            code="invalid_sort",
        )
    return stmt.order_by(column.desc() if descending else column.asc(), default)


def paginate(session: Session, stmt: Select, params: PageParams) -> Page:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(session.scalars(stmt.offset(params.offset).limit(params.size)).unique())
    return Page(items=items, total=total, page=params.page, size=params.size)
