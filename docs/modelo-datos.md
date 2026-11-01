# Modelo de datos

```mermaid
erDiagram
    USERS }o--o| MEMBERS : "cuenta de"
    MEMBERS ||--o{ LOANS : solicita
    MEMBERS ||--o{ RESERVATIONS : realiza
    MEMBERS ||--o{ FINES : adeuda
    CATEGORIES ||--o{ BOOKS : clasifica
    BOOKS }o--o{ AUTHORS : "book_authors"
    BOOKS ||--o{ COPIES : "tiene ejemplares"
    BOOKS ||--o{ RESERVATIONS : "cola de"
    COPIES ||--o{ LOANS : "se presta en"
    COPIES |o--o{ RESERVATIONS : "apartado para"
    LOANS ||--o| FINES : genera

    USERS {
        int id PK
        string email UK
        string full_name
        string password_hash
        string role "admin | bibliotecario | socio"
        bool is_active
        int member_id FK "UK, solo rol socio"
        datetime created_at
    }
    MEMBERS {
        int id PK
        string card_number UK "BIB-2026-0001"
        string full_name
        string email UK
        string document_id UK
        string phone
        string member_type "estudiante | docente | externo"
        bool is_active
        datetime created_at
    }
    AUTHORS {
        int id PK
        string name UK
        string nationality
    }
    CATEGORIES {
        int id PK
        string name UK
        string description
    }
    BOOKS {
        int id PK
        string isbn UK
        string title
        string publisher
        int publication_year
        int category_id FK
        datetime created_at
    }
    COPIES {
        int id PK
        int book_id FK
        string inventory_code UK "INV-00001-001"
        string status "disponible | prestado | apartado | mantenimiento | perdido"
        string location
        datetime created_at
    }
    LOANS {
        int id PK
        int copy_id FK
        int member_id FK
        datetime loaned_at
        date due_date
        datetime returned_at
        int renewals_count
        string status "activo | devuelto"
    }
    RESERVATIONS {
        int id PK
        int book_id FK
        int member_id FK
        string status "pendiente | lista | atendida | cancelada | expirada"
        datetime created_at "orden FIFO"
        int copy_id FK "ejemplar apartado"
        datetime ready_at
        datetime expires_at
        datetime closed_at
    }
    FINES {
        int id PK
        int loan_id FK "UK: una multa por préstamo"
        int member_id FK
        int days_late
        int amount_cents
        string status "pendiente | pagada"
        datetime created_at
        datetime paid_at
    }
```

## Tablas

### `users`
Cuentas de acceso. El rol determina qué endpoints puede usar. Un usuario con rol `socio` está vinculado a un registro de `members` (`member_id` único), lo que permite al backend filtrar automáticamente sus datos. Las contraseñas se guardan con **bcrypt**.

### `members`
Socios de la biblioteca. Se separan de `users` porque **no todo socio usa el sistema**: muchos solo se acercan al mostrador. El `card_number` se genera automáticamente (`BIB-<año>-<correlativo>`) y es lo que se escanea al prestar. `member_type` define la política de préstamo.

### `authors`, `categories`, `book_authors`
Catálogos auxiliares. Un libro puede tener varios autores (relación N:M).

### `books`
La **obra** (el título). No se presta directamente: se prestan sus ejemplares. Las reservas se hacen sobre el libro porque al socio le da igual qué ejemplar recibe.

### `copies`
El **objeto físico** con su código de inventario. Su `status` refleja dónde está:

```mermaid
stateDiagram-v2
    [*] --> disponible
    disponible --> prestado: préstamo
    prestado --> disponible: devolución sin cola
    prestado --> apartado: devolución con cola
    apartado --> prestado: lo retira el reservante
    apartado --> apartado: expira y pasa al siguiente
    apartado --> disponible: expira/cancela sin más cola
    disponible --> mantenimiento
    mantenimiento --> disponible
    mantenimiento --> apartado: vuelve y hay cola
    disponible --> perdido
```

`prestado` y `apartado` solo los asigna el sistema; el personal solo puede poner `disponible`, `mantenimiento` o `perdido`, y no sobre ejemplares en circulación.

### `loans`
Un préstamo de un ejemplar a un socio. `due_date` es una fecha (sin hora): la multa se calcula en días completos. `renewals_count` controla el máximo de renovaciones. El índice `(member_id, status)` acelera las verificaciones de límite.

### `reservations`
Cola FIFO por libro: las pendientes se ordenan por `created_at, id`. Cuando un ejemplar vuelve a circular, la primera pasa a `lista`, recibe `copy_id` y `expires_at`. Estados finales: `atendida` (se convirtió en préstamo), `cancelada`, `expirada`. El índice `(book_id, status, created_at)` sirve directamente a la consulta de la cola.

### `fines`
Multa generada al devolver con retraso. `amount_cents` evita errores de punto flotante. `loan_id` es único: un préstamo genera como máximo una multa. La deuda del socio es la suma de sus multas `pendiente`.

## Convenciones

- **Enums como VARCHAR** (`native_enum=False`): portables y fáciles de migrar si se agregan estados.
- **Fechas en UTC**: el tipo `UTCDateTime` guarda sin zona y devuelve con `tzinfo=UTC`.
- **Claves foráneas activas en SQLite** mediante `PRAGMA foreign_keys=ON` en cada conexión.
- **Unicidad en BD** (ISBN, código de inventario, carnet, correo, DNI) además de la validación en servicios: la BD es la última línea de defensa ante peticiones concurrentes.
