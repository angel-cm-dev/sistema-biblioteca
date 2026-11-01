"""Esquema + datos de demostración FICTICIOS.

Uso:
    python -m app.seed           # crea tablas y carga datos si la BD está vacía
    python -m app.seed --reset   # borra todo y vuelve a cargar

En lugar de insertar préstamos "a mano", el seed reproduce 45 días de operación usando los
MISMOS servicios que la API con un `FixedClock` que avanza: así los datos de ejemplo
(multas, reservas, morosos) son coherentes con las reglas de negocio por construcción.
Los ISBN son ficticios (prefijo 978-612) pero con dígito de control válido.
"""

import argparse
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.actor import Actor
from app.application.services.catalog_service import CatalogService
from app.application.services.fine_service import FineService
from app.application.services.loan_service import LoanService
from app.application.services.member_service import MemberService
from app.application.services.reservation_service import ReservationService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.domain.clock import Clock, FixedClock, SystemClock
from app.domain.enums import MemberType, Role
from app.domain.errors import DomainError
from app.infrastructure.database import Base, build_engine, build_session_factory
from app.infrastructure.models import Fine, Loan, User
from app.schemas.catalog import AuthorCreate, BookCreate, CategoryCreate
from app.schemas.members import MemberCreate

logger = logging.getLogger("app.seed")

DEMO_PASSWORD = "Demo123!"


def isbn13(seq: int) -> str:
    base = f"978612{seq:06d}"
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    return f"{base}{(10 - total % 10) % 10}"


CATEGORIES = [
    ("Literatura peruana", "Narrativa y poesía de autores peruanos"),
    ("Literatura latinoamericana", "Clásicos del boom y posteriores"),
    ("Ingeniería de software", "Diseño, arquitectura y buenas prácticas"),
    ("Bases de datos", "Modelado, SQL y administración"),
    ("Matemáticas", "Cálculo, álgebra y estadística"),
    ("Historia", "Historia del Perú y universal"),
]

AUTHORS = [
    ("Mario Vargas Llosa", "Peruana"),
    ("José María Arguedas", "Peruana"),
    ("César Vallejo", "Peruana"),
    ("Ciro Alegría", "Peruana"),
    ("Gabriel García Márquez", "Colombiana"),
    ("Julio Cortázar", "Argentina"),
    ("Isabel Allende", "Chilena"),
    ("Robert C. Martin", "Estadounidense"),
    ("Martin Fowler", "Británica"),
    ("Eric Evans", "Estadounidense"),
    ("Ramez Elmasri", "Estadounidense"),
    ("Shamkant B. Navathe", "Estadounidense"),
    ("Jorge Basadre", "Peruana"),
    ("James Stewart", "Canadiense"),
]

# (título, autores, categoría, editorial, año, ejemplares)
BOOKS = [
    ("La ciudad y los perros", ["Mario Vargas Llosa"], 0, "Alfaguara", 1963, 2),
    ("Conversación en La Catedral", ["Mario Vargas Llosa"], 0, "Alfaguara", 1969, 1),
    ("Los ríos profundos", ["José María Arguedas"], 0, "Losada", 1958, 1),
    ("Los heraldos negros", ["César Vallejo"], 0, "Editorial Peisa", 1918, 2),
    ("El mundo es ancho y ajeno", ["Ciro Alegría"], 0, "Ercilla", 1941, 1),
    ("Cien años de soledad", ["Gabriel García Márquez"], 1, "Sudamericana", 1967, 1),
    ("Rayuela", ["Julio Cortázar"], 1, "Sudamericana", 1963, 1),
    ("La casa de los espíritus", ["Isabel Allende"], 1, "Plaza & Janés", 1982, 2),
    ("Código limpio", ["Robert C. Martin"], 2, "Anaya", 2012, 2),
    ("Refactorización", ["Martin Fowler"], 2, "Addison-Wesley", 2019, 1),
    ("Diseño guiado por el dominio", ["Eric Evans"], 2, "Addison-Wesley", 2003, 1),
    (
        "Fundamentos de sistemas de bases de datos",
        ["Ramez Elmasri", "Shamkant B. Navathe"],
        3,
        "Pearson",
        2007,
        3,
    ),
    ("Historia de la República del Perú", ["Jorge Basadre"], 5, "Editorial Universitaria", 1968, 1),
    ("Cálculo de una variable", ["James Stewart"], 4, "Cengage", 2012, 2),
]

# Socios ficticios: (nombre, correo, DNI, teléfono, tipo)
MEMBERS = [
    ("Lucía Quispe Mamani", "socio@demo.pe", "70000001", "987000001", MemberType.STUDENT),
    ("Carlos Huamán Rojas", "carlos.huaman@demo.pe", "70000002", "987000002", MemberType.TEACHER),
    ("María Torres Vega", "maria.torres@demo.pe", "70000003", "987000003", MemberType.STUDENT),
    ("Jorge Paredes Cáceres", "jorge.paredes@demo.pe", "70000004", None, MemberType.EXTERNAL),
    ("Ana Flores Ramírez", "ana.flores@demo.pe", "70000005", "987000005", MemberType.STUDENT),
    ("Diego Chávez Medina", "diego.chavez@demo.pe", "70000006", None, MemberType.TEACHER),
    ("Rosa Mendoza Salazar", "rosa.mendoza@demo.pe", "70000007", "987000007", MemberType.EXTERNAL),
    ("Miguel Ríos Castillo", "miguel.rios@demo.pe", "70000008", None, MemberType.STUDENT),
]


def seed_if_empty(session: Session, settings: Settings, clock: Clock | None = None) -> bool:
    if session.scalar(select(User.id).limit(1)) is not None:
        logger.info("seed_skipped", extra={"reason": "la base de datos ya tiene datos"})
        return False
    clock = clock or SystemClock()
    seed(session, settings, clock.now())
    return True


def seed(session: Session, settings: Settings, now) -> None:
    sim = FixedClock(now - timedelta(days=46))
    catalog = CatalogService(session, settings, sim)
    members_svc = MemberService(session, settings, sim)
    loans = LoanService(session, settings, sim)
    reservations = ReservationService(session, settings, sim)
    fines = FineService(session, settings, sim)

    # ---- Usuarios del personal --------------------------------------------------------------
    pwd = hash_password(DEMO_PASSWORD, settings.bcrypt_rounds)
    for email, name, role in [
        ("admin@demo.pe", "Administrador Demo", Role.ADMIN),
        ("bibliotecario@demo.pe", "Bibliotecario Demo", Role.LIBRARIAN),
    ]:
        session.add(
            User(
                email=email,
                full_name=name,
                password_hash=pwd,
                role=role,
                is_active=True,
                created_at=sim.now(),
            )
        )
    session.commit()
    staff = Actor(user_id=2, role=Role.LIBRARIAN)

    # ---- Catálogo -----------------------------------------------------------------------
    cats = [catalog.create_category(CategoryCreate(name=n, description=d)) for n, d in CATEGORIES]
    authors = {
        n: catalog.create_author(AuthorCreate(name=n, nationality=nat)) for n, nat in AUTHORS
    }
    books = {}
    for i, (title, author_names, cat_idx, publisher, year, copies) in enumerate(BOOKS, start=1):
        books[title] = catalog.create_book(
            BookCreate(
                isbn=isbn13(i),
                title=title,
                publisher=publisher,
                publication_year=year,
                category_id=cats[cat_idx].id,
                author_ids=[authors[a].id for a in author_names],
                initial_copies=copies,
            )
        )

    # ---- Socios (solo el primero tiene cuenta de acceso: socio@demo.pe) -----------------
    members = []
    for idx, (name, email, dni, phone, mtype) in enumerate(MEMBERS):
        members.append(
            members_svc.create(
                MemberCreate(
                    full_name=name,
                    email=email,
                    document_id=dni,
                    phone=phone,
                    member_type=mtype,
                    password=DEMO_PASSWORD if idx == 0 else None,
                )
            )
        )
    card = {i + 1: m.card_number for i, m in enumerate(members)}

    def code(title: str, n: int = 1) -> str:
        return books[title].copies[n - 1].inventory_code

    def loan_id(member_idx: int, title: str) -> int:
        stmt = select(Loan.id).where(
            Loan.member_id == members[member_idx - 1].id, Loan.returned_at.is_(None)
        )
        for lid in session.scalars(stmt):
            if loans.loans.get(lid).copy.book_id == books[title].id:
                return lid
        raise DomainError(f"No hay préstamo activo de '{title}' para el socio {member_idx}")

    def at(day: int, *actions) -> None:
        sim.set(now + timedelta(days=day, minutes=-5))  # nunca en el futuro
        for action in actions:
            try:
                action()
            except DomainError as exc:  # el seed nunca debe romperse por una regla
                logger.warning("seed_action_skipped", extra={"day": day, "detail": exc.detail})

    def borrow(m: int, title: str, n: int = 1):
        return lambda: loans.checkout(card_number=card[m], inventory_code=code(title, n))

    def give_back(m: int, title: str):
        return lambda: loans.return_loan(loan_id(m, title))

    def reserve(m: int, title: str):
        return lambda: reservations.create(
            book_id=books[title].id, member_id=members[m - 1].id, actor=staff
        )

    def pay_first_fine(m: int):
        def _pay():
            fine_id = session.scalar(
                select(Fine.id).where(Fine.member_id == members[m - 1].id).limit(1)
            )
            if fine_id:
                fines.pay(fine_id)

        return _pay

    # ---- 45 días de operación simulada ---------------------------------------------------
    at(-45, borrow(2, "Código limpio"), borrow(3, "Cien años de soledad"),
       borrow(1, "La ciudad y los perros"), borrow(4, "Rayuela"))  # fmt: skip
    at(-40, borrow(8, "Fundamentos de sistemas de bases de datos"))
    at(-35, give_back(3, "Cien años de soledad"), borrow(5, "Cien años de soledad"),
       borrow(6, "Refactorización"), borrow(6, "Diseño guiado por el dominio"))  # fmt: skip
    at(-31, give_back(1, "La ciudad y los perros"))
    at(-28, give_back(8, "Fundamentos de sistemas de bases de datos"),
       borrow(3, "Fundamentos de sistemas de bases de datos"))  # fmt: skip
    at(-26, give_back(4, "Rayuela"))  # 12 días tarde -> multa S/ 12 -> bloqueado por deuda
    at(-25, give_back(2, "Código limpio"), borrow(8, "Código limpio"))
    at(-20, give_back(5, "Cien años de soledad"), borrow(7, "Cien años de soledad"))
    at(-19, pay_first_fine(5))
    at(-18, borrow(1, "Los ríos profundos"), borrow(2, "Rayuela"))
    at(-15, reserve(3, "Los ríos profundos"), reserve(5, "Los ríos profundos"))
    at(-12, borrow(5, "La ciudad y los perros"), borrow(1, "Código limpio", 2))
    at(-10, give_back(8, "Código limpio"))
    at(-6, give_back(3, "Fundamentos de sistemas de bases de datos"),
       borrow(2, "Fundamentos de sistemas de bases de datos"))  # fmt: skip
    at(-5, give_back(1, "Los ríos profundos"))  # queda apartado para el socio 3 (FIFO)
    at(-1, reservations.expire_holds)  # el socio 3 no recogió: pasa al socio 5
    at(0, borrow(8, "Cálculo de una variable"), borrow(1, "La casa de los espíritus"),
       reserve(1, "Rayuela"))  # fmt: skip
    session.commit()
    logger.info("seed_completed", extra={"members": len(members), "books": len(books)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea el esquema y carga datos demo")
    parser.add_argument("--reset", action="store_true", help="Borra y recrea todas las tablas")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with build_session_factory(engine)() as session:
        seed_if_empty(session, settings)


if __name__ == "__main__":
    main()
