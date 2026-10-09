from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.user import UserRole


@pytest.fixture
def authenticated_clinic_client(client: TestClient) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.registry_officer)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_clinic_client(client: TestClient) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.administrator)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_anonymous_cannot_list_clinics(client: TestClient) -> None:
    response = client.get("/api/v1/clinics")
    assert response.status_code == 401


def test_registry_officer_can_list_clinics(authenticated_clinic_client: TestClient, sample_clinic) -> None:
    response = authenticated_clinic_client.get("/api/v1/clinics")
    assert response.status_code == 200
    assert any(clinic["id"] == sample_clinic.id for clinic in response.json())


def test_admin_can_create_clinic(admin_clinic_client: TestClient) -> None:
    response = admin_clinic_client.post(
        "/api/v1/clinics",
        json={"name": "Kabwe General Hospital", "location": "Kabwe"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Kabwe General Hospital"
    assert response.json()["location"] == "Kabwe"


def test_non_admin_cannot_create_clinic(authenticated_clinic_client: TestClient) -> None:
    response = authenticated_clinic_client.post(
        "/api/v1/clinics",
        json={"name": "Kabwe General Hospital", "location": "Kabwe"},
    )
    assert response.status_code == 403


def test_get_clinic_returns_404_for_unknown_id(authenticated_clinic_client: TestClient) -> None:
    response = authenticated_clinic_client.get("/api/v1/clinics/not-a-clinic")
    assert response.status_code == 404
