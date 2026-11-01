# ADR 0003: SQLite por defecto y esquema con `create_all` (sin Alembic por ahora)

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

El proyecto debe levantarse con un solo comando, correr pruebas sin Docker y poder pasar a PostgreSQL sin reescribir código.

## Decisión

- **SQLite** como base por defecto: en Docker vive en un volumen nombrado (`biblioteca-data`); en pruebas, en memoria con `StaticPool`.
- El esquema se crea con `Base.metadata.create_all()` (idempotente) al iniciar la app o con `python -m app.seed`. No se usa Alembic todavía.
- El modelo evita características específicas del motor: enums como `VARCHAR`, dinero en céntimos (`INTEGER`), fechas UTC sin zona.
- La URL de conexión se toma de `DATABASE_URL`.

## Consecuencias

- (+) Cero dependencias externas para la demo y la CI.
- (+) Cambiar a PostgreSQL = instalar `psycopg` y cambiar `DATABASE_URL` (ver README).
- (-) `create_all` no modifica tablas existentes: ante cambios de esquema en un entorno con datos reales hay que adoptar **Alembic** (`alembic init`, `target_metadata = Base.metadata`, `alembic revision --autogenerate`). Está en el roadmap.
- (-) SQLite serializa escrituras; con múltiples workers y alta concurrencia se debe migrar a PostgreSQL y bloquear filas al prestar (`SELECT ... FOR UPDATE`).
