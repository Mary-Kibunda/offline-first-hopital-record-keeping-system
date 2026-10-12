"""Isolated SQLite fixtures for API and service tests."""

import os
from collections.abc import Generator
from datetime import date

os.environ.update(
    {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "SECRET_KEY": "test-only-signing-key-never-use-in-production",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "480",
    }
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.clinic import Clinic
from app.models.patient import Gender, Patient
from app.models.user import User, UserRole

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Generator[None, None, None]:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
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
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
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
def sample_patient(db_session: Session, sample_clinic: Clinic) -> Patient:
    patient = Patient(
        registered_clinic_id=sample_clinic.id,
        first_name="Mwamba",
        last_name="Banda",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.male,
    )
    db_session.add(patient)
    db_session.flush()
    return patient


@pytest.fixture
def auth_client(client: TestClient, sample_registry_officer: User) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: sample_registry_officer
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_client(client: TestClient, sample_admin: User) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: sample_admin
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def with_role(client: TestClient, db_session: Session, sample_clinic: Clinic):
    def _use_role(role: UserRole) -> User:
        user = User(
            name=role.value.replace("_", " ").title(),
            username=f"test-{role.value}",
            role=role,
            clinic_id=sample_clinic.id,
            password_hash=hash_password("password123"),
        )
        db_session.add(user)
        db_session.flush()
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    yield _use_role
    app.dependency_overrides.pop(get_current_user, None)
