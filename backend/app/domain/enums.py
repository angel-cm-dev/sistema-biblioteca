"""Enumeraciones del dominio. Heredan de `str` para serializarse tal cual en JSON y en BD."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    LIBRARIAN = "bibliotecario"
    MEMBER = "socio"


class MemberType(StrEnum):
    STUDENT = "estudiante"
    TEACHER = "docente"
    EXTERNAL = "externo"


class CopyStatus(StrEnum):
    AVAILABLE = "disponible"
    LOANED = "prestado"
    ON_HOLD = "apartado"  # reservado para el primer socio de la cola
    MAINTENANCE = "mantenimiento"
    LOST = "perdido"


class LoanStatus(StrEnum):
    ACTIVE = "activo"
    RETURNED = "devuelto"


class ReservationStatus(StrEnum):
    PENDING = "pendiente"  # en cola, esperando un ejemplar
    READY = "lista"  # ejemplar apartado, el socio debe recogerlo antes de expires_at
    FULFILLED = "atendida"  # se convirtió en préstamo
    CANCELLED = "cancelada"
    EXPIRED = "expirada"


class FineStatus(StrEnum):
    PENDING = "pendiente"
    PAID = "pagada"
