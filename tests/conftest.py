"""Shared pytest fixtures.

The API talks to Postgres in production, but the tests drive it through an
in-memory SQLite database by overriding the ``get_db`` dependency. That keeps
the suite fast and dependency-free while still exercising the real routes,
dependency wiring and role guards.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

API = "/api/v1"
DEFAULT_PASSWORD = "supersecret123"


@pytest.fixture()
def db_session():
    """A fresh in-memory database per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """A TestClient wired to the in-memory database."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_user(
    db_session,
    email: str,
    password: str = DEFAULT_PASSWORD,
    role: UserRole = UserRole.USER,
    is_active: bool = True,
) -> User:
    """Insert a user directly, bypassing the API."""
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=get_password_hash(password),
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client, email: str, password: str = DEFAULT_PASSWORD) -> str:
    """Log in and return the bearer token."""
    response = client.post(
        f"{API}/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(client, email: str, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    """Convenience wrapper returning an Authorization header for ``email``."""
    return {"Authorization": f"Bearer {login(client, email, password)}"}
