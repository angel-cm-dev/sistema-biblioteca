"""Punto de entrada: fábrica de la aplicación FastAPI.

`create_app()` recibe configuración, reloj y engine opcionales: en producción usa los valores
por defecto y en pruebas se inyecta SQLite en memoria y un `FixedClock`.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text

from app.api.errors import register_error_handlers
from app.api.routers import auth, catalog, circulation, members, reports
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.domain.clock import Clock, SystemClock
from app.infrastructure.database import Base, build_engine, build_session_factory

logger = logging.getLogger("app.http")
API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None, clock: Clock | None = None, engine: Engine | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = engine or build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Crea el esquema si no existe (idempotente). Ver docs/decisiones/0003 sobre Alembic.
        Base.metadata.create_all(engine)
        if settings.seed_on_startup:
            from app.seed import seed_if_empty

            with app.state.session_factory() as session:
                seed_if_empty(session, settings, app.state.clock)
        logger.info("startup", extra={"environment": settings.environment})
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "API de gestión de biblioteca: catálogo, ejemplares, socios, préstamos, "
            "renovaciones, reservas con cola FIFO, multas y reportes. "
            "Autentíquese en **POST /api/v1/auth/login** y use el botón *Authorize*."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        # Un id por petición (propagado o generado) para correlacionar logs entre servicios.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        return response

    register_error_handlers(app)

    for router in (
        auth.router,
        members.router,
        catalog.router,
        circulation.loans,
        circulation.reservations,
        circulation.fines,
        reports.router,
    ):
        app.include_router(router, prefix=API_PREFIX)

    @app.get("/health", tags=["Salud"], summary="Estado del servicio y de la base de datos")
    def health() -> JSONResponse:
        # Lo usan el healthcheck de Docker y los balanceadores: 503 si la BD no responde.
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:  # pragma: no cover - depende de la infraestructura
            logger.exception("healthcheck_failed")
            return JSONResponse({"status": "degraded", "database": "error"}, status_code=503)
        return JSONResponse({"status": "ok", "database": "ok"})

    return app
