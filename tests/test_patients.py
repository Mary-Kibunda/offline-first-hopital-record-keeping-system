"""
Shared pytest fixtures.

Tests run against a real PostgreSQL database (health_chart), not
SQLite-in-memory — this project's schema uses PostgreSQL-specific behaviour
in a few places (portable-but-still-checked enum columns, timezone-aware
DateTime columns), and testing against a different database engine than
production risks passing tests that would fail for real. Each test runs
inside a transaction that is rolled back afterwards, so tests never leak
data into one another and the suite can run repeatedly without resetting
the database by hand.
"""
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:cookie45%3F%21@localhost:5432/health_chart"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-local-dev-only")

from app.api.deps import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.clinic import Clinic  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(TEST_DATABASE_URL, future=True)
TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Generator[None, None, None]:
    """Tables already exist (created via Alembic against health_chart);
    this just guarantees they're there even if someone runs the suite
    against a fresh database, without duplicating Alembic's migration
    logic."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    One session per test, wrapped in a transaction that is always rolled
    back — so every test starts from a clean slate without needing to
    truncate tables manually.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose requests use the same rolled-back-per-test session."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_clinic(db_session: Session) -> Clinic:
    clinic = Clinic(name="Chongwe First-Level Hospital", location="Chongwe")
    db_session.add(clinic)
    db_session.flush()
    return clinic


@pytest.fixture
def sample_admin(db_session: Session, sample_clinic: Clinic) -> User:
    admin = User(
        name="Ruth Mwape",
        username="r.mwape",
        role=UserRole.administrator,
        clinic_id=sample_clinic.id,
        password_hash=hash_password("adminpass123"),
    )
    db_session.add(admin)
    db_session.flush()
    return admin


@pytest.fixture
def sample_registry_officer(db_session: Session, sample_clinic: Clinic) -> User:
    user = User(
        name="Mutinta Banda",
        username="m.banda",
        role=UserRole.registry_officer,
        clinic_id=sample_clinic.id,
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def auth_client(client: TestClient, sample_registry_officer: User) -> Generator[TestClient, None, None]:
    """A TestClient pre-authenticated as a registry officer."""

    def _override_current_user() -> User:
        return sample_registry_officer

    app.dependency_overrides[get_current_user] = _override_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_client(client: TestClient, sample_admin: User) -> Generator[TestClient, None, None]:
    """A TestClient pre-authenticated as an administrator."""

    def _override_current_user() -> User:
        return sample_admin

    app.dependency_overrides[get_current_user] = _override_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)