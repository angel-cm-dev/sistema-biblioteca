"""Tipos de paginación compartidos entre capas (independientes de HTTP y de SQL)."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int = 1
    size: int = 20
    sort: str | None = None  # "campo" ascendente, "-campo" descendente

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(slots=True)
class Page[T]:
    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return math.ceil(self.total / self.size) if self.size else 0
