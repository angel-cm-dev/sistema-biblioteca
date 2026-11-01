# Guía de la API con ejemplos `curl`

Base: `http://localhost:8000/api/v1` (o `http://localhost:8080/api/v1` a través de nginx).
Documentación interactiva: `http://localhost:8000/docs`.

> En Windows PowerShell use `curl.exe` y comillas dobles escapadas, o pruebe directamente desde Swagger.

## 1. Autenticación

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bibliotecario@demo.pe","password":"Demo123!"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": 2, "email": "bibliotecario@demo.pe", "role": "bibliotecario", "...": "..." }
}
```

Guarde el token para las siguientes llamadas:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bibliotecario@demo.pe","password":"Demo123!"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
```

## 2. Catálogo

```bash
# Búsqueda por título/ISBN/autor, con filtros, orden y paginación
curl -s "http://localhost:8000/api/v1/books?q=vargas&available=true&sort=-publication_year&page=1&size=10" -H "$AUTH"

# Detalle con ejemplares y longitud de la cola de reservas
curl -s http://localhost:8000/api/v1/books/1 -H "$AUTH"

# Registrar un libro con 2 ejemplares (ISBN validado con dígito de control)
curl -s -X POST http://localhost:8000/api/v1/books -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"isbn":"978-0-306-40615-7","title":"Libro de ejemplo","author_ids":[1],"category_id":1,"initial_copies":2}'

# Agregar un ejemplar y enviarlo a mantenimiento
curl -s -X POST http://localhost:8000/api/v1/books/1/copies -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"location":"Estante A-3"}'
curl -s -X PATCH http://localhost:8000/api/v1/copies/5/status -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"status":"mantenimiento"}'
```

## 3. Socios

```bash
# Registrar socio (con cuenta de acceso opcional)
curl -s -X POST http://localhost:8000/api/v1/members -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"full_name":"Pedro Sánchez Ruiz","email":"pedro@demo.pe","document_id":"71234567","member_type":"estudiante","password":"Clave1234"}'

# Situación: límites, deuda y motivos de bloqueo
curl -s http://localhost:8000/api/v1/members/4/status -H "$AUTH"
```

## 4. Préstamos

```bash
# Prestar por carnet + código de inventario
curl -s -X POST http://localhost:8000/api/v1/loans -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"card_number":"BIB-2026-0003","inventory_code":"INV-00004-001"}'

# Préstamos vencidos
curl -s "http://localhost:8000/api/v1/loans?overdue=true" -H "$AUTH"

# Renovar y devolver
curl -s -X POST http://localhost:8000/api/v1/loans/10/renew  -H "$AUTH"
curl -s -X POST http://localhost:8000/api/v1/loans/10/return -H "$AUTH"
```

Respuesta de devolución con retraso y cola de reservas:

```json
{
  "loan": { "id": 10, "status": "devuelto", "...": "..." },
  "fine": { "id": 5, "days_late": 3, "amount": "3.00", "status": "pendiente", "...": "..." },
  "reserved_for": { "id": 4, "status": "lista", "expires_at": "2026-11-04T15:00:00Z", "...": "..." }
}
```

## 5. Reservas

```bash
# Como socio: reservar un libro sin ejemplares disponibles
curl -s -X POST http://localhost:8000/api/v1/reservations -H "Authorization: Bearer $TOKEN_SOCIO" \
  -H "Content-Type: application/json" -d '{"book_id":7}'

# Cancelar
curl -s -X POST http://localhost:8000/api/v1/reservations/4/cancel -H "$AUTH"

# Expirar apartados no recogidos (job de mantenimiento)
curl -s -X POST http://localhost:8000/api/v1/reservations/expire-holds -H "$AUTH"
```

## 6. Multas y reportes

```bash
curl -s "http://localhost:8000/api/v1/fines?status=pendiente" -H "$AUTH"
curl -s -X POST http://localhost:8000/api/v1/fines/5/pay -H "$AUTH"

curl -s http://localhost:8000/api/v1/reports/summary -H "$AUTH"
curl -s "http://localhost:8000/api/v1/reports/most-borrowed?limit=5&date_from=2026-10-01&date_to=2026-10-31" -H "$AUTH"
curl -s http://localhost:8000/api/v1/reports/delinquency -H "$AUTH"
```

## Paginación, filtros y orden

Los listados devuelven:

```json
{ "items": [], "total": 42, "page": 2, "size": 10, "pages": 5 }
```

- `page` (desde 1) y `size` (1-100).
- `sort=campo` ascendente, `sort=-campo` descendente. Solo se aceptan columnas de una lista blanca; otra columna devuelve `400 invalid_sort`.

## Errores (ProblemDetails, RFC 7807)

Todas las respuestas de error usan `Content-Type: application/problem+json`:

| Status | `code` | Cuándo |
|---|---|---|
| 400 | `invalid_sort`, `invalid_range`, `bad_request` | Parámetros incoherentes |
| 401 | `unauthorized`, `invalid_credentials`, `invalid_token`, `token_expired` | Sin token, token inválido o credenciales incorrectas |
| 403 | `forbidden` | Rol insuficiente o recurso de otro socio |
| 404 | `not_found` | Recurso inexistente |
| 409 | `conflict`, `copy_on_hold`, `copy_unavailable`, `already_returned`, `already_paid`, `isbn_taken`, `email_taken`, `duplicate`, `integrity_error` | Estado actual impide la operación o duplicado |
| 422 | `validation_error` | Datos de entrada inválidos (incluye `errors[]` por campo) |
| 422 | `loan_limit_reached`, `member_blocked`, `renewal_not_allowed`, `copies_available`, `already_loaned`, `same_title_on_loan`, `member_inactive` | Regla de negocio incumplida |
| 500 | `internal_error` | Error inesperado (se registra con `request_id`) |

### loan_limit_reached
El socio alcanzó el máximo de préstamos simultáneos de su tipo.

### member_blocked
El socio tiene deuda ≥ umbral, préstamos vencidos o está inactivo.

### renewal_not_allowed
Préstamo vencido, máximo de renovaciones alcanzado o hay reservas pendientes del libro.

### copy_on_hold
El ejemplar está apartado para otro socio de la cola.

### copies_available
Se intentó reservar un libro que tiene ejemplares disponibles: corresponde pedir el préstamo.

Ejemplo de error de validación:

```json
{
  "type": "https://github.com/angel-cm-dev/sistema-biblioteca/blob/main/docs/guia-api.md#validation_error",
  "title": "Datos de entrada inválidos",
  "status": 422,
  "detail": "Uno o más campos no son válidos",
  "instance": "/api/v1/members",
  "code": "validation_error",
  "request_id": "b3c1f0...",
  "errors": [
    { "field": "email", "message": "value is not a valid email address: ...", "type": "value_error" },
    { "field": "document_id", "message": "String should match pattern '^\\d{8,12}$'", "type": "string_pattern_mismatch" }
  ]
}
```
