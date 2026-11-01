"""Excepciones del dominio.

Los servicios lanzan estas excepciones sin saber nada de HTTP. La capa API las traduce a
respuestas ProblemDetails (RFC 7807) en un único manejador global, de modo que los códigos de
estado son consistentes en toda la API.
"""


class DomainError(Exception):
    status_code = 400
    title = "Solicitud inválida"
    code = "bad_request"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code


class NotFoundError(DomainError):
    status_code = 404
    title = "Recurso no encontrado"
    code = "not_found"


class ConflictError(DomainError):
    """El recurso ya existe o su estado actual impide la operación (p.ej. ejemplar prestado)."""

    status_code = 409
    title = "Conflicto"
    code = "conflict"


class BusinessRuleError(DomainError):
    """Se violó una regla de negocio (límite de préstamos, bloqueo por deuda, etc.)."""

    status_code = 422
    title = "Regla de negocio incumplida"
    code = "business_rule"


class AuthenticationError(DomainError):
    status_code = 401
    title = "No autenticado"
    code = "unauthorized"


class PermissionDeniedError(DomainError):
    status_code = 403
    title = "Acceso denegado"
    code = "forbidden"
