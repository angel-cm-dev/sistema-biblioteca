from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.application.pagination import Page

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base de todos los DTOs: permite construirlos desde objetos ORM (`from_attributes`)."""

    model_config = ConfigDict(from_attributes=True)


class PageOut(ApiModel, Generic[T]):  # noqa: UP046 - Generic explícito, compatible con pydantic
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, page: Page, items: list[T]) -> "PageOut[T]":
        return cls(items=items, total=page.total, page=page.page, size=page.size, pages=page.pages)


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


class MessageOut(ApiModel):
    message: str
