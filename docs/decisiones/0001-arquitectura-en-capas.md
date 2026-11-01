# ADR 0001: Arquitectura en capas pragmática

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

El sistema tiene reglas de negocio no triviales (límites por tipo de socio, multas, renovaciones condicionadas, cola de reservas, bloqueos). Queremos que esas reglas sean fáciles de leer y probar, pero sin la ceremonia de una arquitectura hexagonal completa (entidades de dominio duplicadas, mapeadores, puertos para cada repositorio), desproporcionada para el tamaño del proyecto.

## Decisión

- Cuatro capas: `api` → `application` → (`domain`, `infrastructure`).
- Los **modelos ORM** de SQLAlchemy son las entidades persistentes; viven en `infrastructure`.
- Las **reglas puras** se extraen a `domain/policies.py` como funciones sin I/O (`days_late`, `fine_amount_cents`, `is_blocked_by_debt`, `renewal_rejection_reason`...).
- Los **servicios** de `application` orquestan: consultan repositorios, aplican políticas, modifican entidades y hacen `commit`.
- Los routers son delgados y solo traducen HTTP ↔ servicio.

## Consecuencias

- (+) Las reglas se prueban con pruebas unitarias instantáneas; los servicios con SQLite en memoria.
- (+) Cambiar FastAPI por otro framework afectaría solo a `api/`.
- (-) Los servicios dependen de los modelos ORM; cambiar de ORM requeriría tocar servicios.
- (-) Hay que mantener la disciplina de no poner reglas en routers ni repositorios (se revisa en code review).
