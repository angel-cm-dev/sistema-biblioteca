"""Reloj inyectable.

Las reglas de la biblioteca dependen del tiempo (vencimientos, multas, expiración de
reservas). Si el código llamara a `datetime.now()` directamente, probar "un préstamo devuelto
5 días tarde" exigiría esperar 5 días o parchear módulos. Con un `Clock` inyectado, las
pruebas usan `FixedClock` y avanzan el tiempo a voluntad con `advance(days=5)`.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    """Reloj real (UTC)."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()


class FixedClock:
    """Reloj controlable para pruebas y demos."""

    def __init__(self, current: datetime) -> None:
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        self._current = current

    def now(self) -> datetime:
        return self._current

    def today(self) -> date:
        return self._current.date()

    def advance(self, *, days: int = 0, hours: int = 0) -> None:
        self._current += timedelta(days=days, hours=hours)

    def set(self, current: datetime) -> None:
        self._current = current if current.tzinfo else current.replace(tzinfo=UTC)
