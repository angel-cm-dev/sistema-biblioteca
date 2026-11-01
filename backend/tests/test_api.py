"""Pruebas de integración de la API (HTTP real contra la app con SQLite en memoria)."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.domain.enums import MemberType, Role
from tests.factories import PASSWORD, Factory

API = "/api/v1"


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def staff_headers(client: TestClient, factory: Factory, role: Role = Role.LIBRARIAN):
    user = factory.staff_user(role)
    return login(client, user.email)


# ---- Infraestructura ----------------------------------------------------------------------


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert "X-Request-ID" in response.headers


def test_openapi_is_available(client: TestClient):
    assert client.get("/openapi.json").json()["info"]["title"]


# ---- Autenticación ------------------------------------------------------------------------


def test_login_wrong_password_returns_problem_details(client: TestClient, factory: Factory):
    user = factory.staff_user()
    response = client.post(f"{API}/auth/login", json={"email": user.email, "password": "x"})
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "invalid_credentials"
    assert body["status"] == 401
    assert body["instance"] == f"{API}/auth/login"


def test_protected_endpoint_requires_token(client: TestClient):
    response = client.get(f"{API}/books")
    assert response.status_code == 401
    assert response.json()["title"] == "No autenticado"


def test_invalid_token_rejected(client: TestClient):
    response = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer basura"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_me_returns_current_user(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory, Role.ADMIN)
    assert client.get(f"{API}/auth/me", headers=headers).json()["role"] == "admin"


# ---- Autorización por rol -----------------------------------------------------------------


def test_member_cannot_access_staff_endpoints(client: TestClient, factory: Factory):
    member = factory.member(password=PASSWORD)
    headers = login(client, member.email)
    assert client.get(f"{API}/members", headers=headers).status_code == 403
    assert client.get(f"{API}/reports/summary", headers=headers).status_code == 403
    response = client.post(
        f"{API}/loans",
        headers=headers,
        json={"card_number": member.card_number, "inventory_code": "INV-1"},
    )
    assert response.status_code == 403


def test_only_admin_manages_users(client: TestClient, factory: Factory):
    librarian = staff_headers(client, factory)
    admin = staff_headers(client, factory, Role.ADMIN)
    payload = {
        "email": "nuevo@test.pe",
        "full_name": "Nuevo Bibliotecario",
        "password": "Segura123",
        "role": "bibliotecario",
    }
    assert client.post(f"{API}/users", headers=librarian, json=payload).status_code == 403
    assert client.post(f"{API}/users", headers=admin, json=payload).status_code == 201
    assert client.post(f"{API}/users", headers=admin, json=payload).status_code == 409


def test_member_only_sees_own_loans_and_fines(client: TestClient, factory: Factory):
    me = factory.member(password=PASSWORD)
    other = factory.member()
    factory.lend(me, factory.book())
    other_loan = factory.lend(other, factory.book())
    headers = login(client, me.email)

    loans = client.get(f"{API}/loans", headers=headers).json()
    assert loans["total"] == 1
    assert loans["items"][0]["member"]["id"] == me.id
    # Aunque intente filtrar por otro socio, el alcance se fuerza a sí mismo
    assert client.get(f"{API}/loans?member_id={other.id}", headers=headers).json()["total"] == 1
    assert client.get(f"{API}/loans/{other_loan.id}", headers=headers).status_code == 403
    assert client.get(f"{API}/fines", headers=headers).json()["total"] == 0
    assert client.get(f"{API}/members/{other.id}", headers=headers).status_code == 403


# ---- Validación ---------------------------------------------------------------------------


def test_validation_errors_list_fields(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    response = client.post(
        f"{API}/members",
        headers=headers,
        json={"full_name": "A", "email": "no-es-correo", "document_id": "12", "member_type": "x"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    fields = {e["field"] for e in body["errors"]}
    assert {"full_name", "email", "document_id", "member_type"} <= fields


def test_invalid_isbn_rejected(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    author = client.post(f"{API}/authors", headers=headers, json={"name": "Autor X"}).json()
    response = client.post(
        f"{API}/books",
        headers=headers,
        json={"isbn": "978-0-306-40615-8", "title": "T", "author_ids": [author["id"]]},
    )
    assert response.status_code == 422
    assert "dígito de control" in response.json()["errors"][0]["message"]


def test_invalid_sort_field_is_rejected(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    response = client.get(f"{API}/books?sort=password", headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_sort"


# ---- Catálogo, búsqueda y paginación ------------------------------------------------------


def test_create_book_with_copies_and_search(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    author = client.post(
        f"{API}/authors", headers=headers, json={"name": "José María Arguedas"}
    ).json()
    category = client.post(f"{API}/categories", headers=headers, json={"name": "Novela"}).json()
    response = client.post(
        f"{API}/books",
        headers=headers,
        json={
            "isbn": "978-0-306-40615-7",
            "title": "Los ríos profundos",
            "author_ids": [author["id"]],
            "category_id": category["id"],
            "initial_copies": 2,
        },
    )
    assert response.status_code == 201, response.text
    book = response.json()
    assert book["total_copies"] == 2 and book["available_copies"] == 2
    assert book["copies"][0]["inventory_code"].startswith("INV-")

    # Búsqueda por autor
    found = client.get(f"{API}/books?q=arguedas", headers=headers).json()
    assert found["total"] == 1 and found["items"][0]["title"] == "Los ríos profundos"
    # ISBN duplicado
    dup = client.post(
        f"{API}/books",
        headers=headers,
        json={"isbn": "9780306406157", "title": "Otro", "author_ids": [author["id"]]},
    )
    assert dup.status_code == 409


def test_pagination_and_sort(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    for title in ["Charlie", "Alfa", "Bravo", "Delta", "Echo"]:
        factory.book(title=title)
    page = client.get(f"{API}/books?page=2&size=2&sort=title", headers=headers).json()
    assert page["total"] == 5 and page["pages"] == 3
    assert [b["title"] for b in page["items"]] == ["Charlie", "Delta"]
    desc = client.get(f"{API}/books?size=1&sort=-title", headers=headers).json()
    assert desc["items"][0]["title"] == "Echo"


def test_filter_available_books(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    lent = factory.book(copies=1, title="Prestado")
    factory.book(copies=1, title="Libre")
    factory.lend(factory.member(), lent)
    titles = [
        b["title"]
        for b in client.get(f"{API}/books?available=true", headers=headers).json()["items"]
    ]
    assert titles == ["Libre"]


# ---- Flujo completo de circulación --------------------------------------------------------


def test_full_circulation_flow(client: TestClient, factory: Factory, clock):
    staff = staff_headers(client, factory)
    book = factory.book(copies=1, title="Rayuela")
    holder = factory.member(MemberType.STUDENT)
    waiting = factory.member(MemberType.TEACHER, password=PASSWORD)
    waiting_headers = login(client, waiting.email)

    # 1. Préstamo por carnet + código de inventario
    response = client.post(
        f"{API}/loans",
        headers=staff,
        json={
            "card_number": holder.card_number.lower(),
            "inventory_code": book.copies[0].inventory_code,
        },
    )
    assert response.status_code == 201, response.text
    loan = response.json()

    # 2. El socio en espera reserva (no hay ejemplares) y queda primero en la cola
    response = client.post(
        f"{API}/reservations", headers=waiting_headers, json={"book_id": book.id}
    )
    assert response.status_code == 201, response.text
    reservation = response.json()
    assert reservation["queue_position"] == 1
    assert reservation["member"]["id"] == waiting.id

    # 3. La renovación está bloqueada por la reserva pendiente
    response = client.post(f"{API}/loans/{loan['id']}/renew", headers=staff)
    assert response.status_code == 422
    assert response.json()["code"] == "renewal_not_allowed"

    # 4. Devolución con 3 días de retraso -> multa y ejemplar apartado
    clock.advance(days=17)
    response = client.post(f"{API}/loans/{loan['id']}/return", headers=staff)
    assert response.status_code == 200
    body = response.json()
    assert body["fine"]["amount"] == "3.00"
    assert body["reserved_for"]["id"] == reservation["id"]
    assert body["reserved_for"]["status"] == "lista"

    # 5. El socio ve su reserva lista
    mine = client.get(f"{API}/reservations", headers=waiting_headers).json()
    assert mine["items"][0]["status"] == "lista"

    # 6. Se le presta el ejemplar apartado y la reserva queda atendida
    response = client.post(
        f"{API}/loans",
        headers=staff,
        json={"card_number": waiting.card_number, "inventory_code": book.copies[0].inventory_code},
    )
    assert response.status_code == 201
    # Docente: 30 días de préstamo
    assert response.json()["due_date"] == str(clock.today() + timedelta(days=30))

    # 7. Pago de la multa del primer socio
    fine_id = body["fine"]["id"]
    assert client.post(f"{API}/fines/{fine_id}/pay", headers=staff).json()["status"] == "pagada"
    assert client.post(f"{API}/fines/{fine_id}/pay", headers=staff).status_code == 409


def test_member_status_endpoint(client: TestClient, factory: Factory):
    member = factory.member(MemberType.EXTERNAL, password=PASSWORD)
    factory.lend(member, factory.book())
    headers = login(client, member.email)
    status = client.get(f"{API}/members/me/status", headers=headers).json()
    assert status["policy"] == {"max_active_loans": 2, "loan_days": 7, "max_renewals": 1}
    assert status["active_loans"] == 1
    assert status["can_borrow"] is True
    assert status["pending_debt"] == "0.00"


def test_not_found_returns_problem(client: TestClient, factory: Factory):
    headers = staff_headers(client, factory)
    response = client.post(
        f"{API}/loans", headers=headers, json={"card_number": "BIB-0000", "inventory_code": "NOPE"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ---- Reportes -----------------------------------------------------------------------------


def test_reports(client: TestClient, factory: Factory, clock):
    headers = staff_headers(client, factory)
    popular = factory.book(copies=2, title="Popular")
    rare = factory.book(copies=1, title="Raro")
    late_member = factory.member()
    other = factory.member()
    factory.lend(late_member, popular, 0)
    factory.lend(other, popular, 1)
    factory.lend(other, rare)

    clock.advance(days=20)
    summary = client.get(f"{API}/reports/summary", headers=headers).json()
    assert summary["active_loans"] == 3
    assert summary["overdue_loans"] == 3

    top = client.get(f"{API}/reports/most-borrowed?limit=1", headers=headers).json()
    assert top == [{"book_id": popular.id, "title": "Popular", "isbn": popular.isbn, "loans": 2}]

    delinquency = client.get(f"{API}/reports/delinquency", headers=headers).json()
    assert {row["member"]["id"] for row in delinquency} == {late_member.id, other.id}
    assert all(row["max_days_overdue"] == 6 and row["is_blocked"] for row in delinquency)
