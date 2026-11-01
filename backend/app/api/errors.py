"""Manejo global de errores con formato ProblemDetails (RFC 7807).

Todas las respuestas de error comparten la misma forma:

    {"type": "...", "title": "...", "status": 422, "detail": "...", "instance": "/api/v1/...",
     "code": "loan_limit_reached", "request_id": "..."}

El frontend puede así mostrar `detail` y reaccionar a `code` sin parsear mensajes.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import DomainError

logger = logging.getLogger("app.errors")

PROBLEM_JSON = "application/problem+json"
TYPE_BASE = "https://github.com/angel-cm-dev/sistema-biblioteca/blob/main/docs/guia-api.md#"


def problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    code: str,
    extra: dict | None = None,
) -> JSONResponse:
    body = {
        "type": f"{TYPE_BASE}{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": getattr(request.state, "request_id", None),
    }
    if extra:
        body.update(extra)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        logger.info(
            "domain_error",
            extra={"code": exc.code, "status": exc.status_code, "detail": exc.detail},
        )
        return problem(
            request, status=exc.status_code, title=exc.title, detail=exc.detail, code=exc.code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p != "body"),
                "message": err["msg"].removeprefix("Value error, "),
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        return problem(
            request,
            status=422,
            title="Datos de entrada inválidos",
            detail="Uno o más campos no son válidos",
            code="validation_error",
            extra={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        titles = {404: "Recurso no encontrado", 405: "Método no permitido"}
        return problem(
            request,
            status=exc.status_code,
            title=titles.get(exc.status_code, "Error HTTP"),
            detail=str(exc.detail),
            code=f"http_{exc.status_code}",
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # Última línea de defensa: los servicios validan duplicados, pero una carrera entre dos
        # peticiones simultáneas puede llegar a la restricción UNIQUE de la base de datos.
        logger.warning("integrity_error", extra={"error": str(exc.orig)})
        return problem(
            request,
            status=409,
            title="Conflicto",
            detail="La operación viola una restricción de integridad (registro duplicado)",
            code="integrity_error",
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return problem(
            request,
            status=500,
            title="Error interno",
            detail="Ocurrió un error inesperado. Intente nuevamente.",
            code="internal_error",
        )
