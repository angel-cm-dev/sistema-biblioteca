"""Fixtures compartidas.

Las pruebas NO necesitan Docker: cada prueba recibe una base SQLite en memoria nueva y un
`FixedClock` que puede adelantarse para simular el paso de los días.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.clock import FixedClock
from app.infrastructure.database import Base, build_engine, build_session_factory
from app.main import create_app
from tests.factories import Factory


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite://",
        jwt_secret="clave-de-pruebas-con-mas-de-32-caracteres",
        bcrypt_rounds=4,  # bcrypt lento en pruebas no aporta nada
        fine_per_day=Decimal("1.00"),
        debt_block_threshold=Decimal("10.00"),
        reservation_hold_days=3,
        log_level="WARNING",
    )


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 3, 2, 15, 0, tzinfo=UTC))


@pytest.fixture
def engine(settings: Settings):
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with build_session_factory(engine)() as session:
        yield session


@pytest.fixture
def factory(session: Session, settings: Settings, clock: FixedClock) -> Factory:
    return Factory(session, settings, clock)


@pytest.fixture
def client(settings: Settings, clock: FixedClock, engine) -> Iterator[TestClient]:
    app = create_app(settings=settings, clock=clock, engine=engine)
    with TestClient(app) as test_client:
        yield test_client
