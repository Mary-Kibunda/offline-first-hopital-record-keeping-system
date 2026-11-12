from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.models.user import User, UserRole


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (
            UserRole.registry_officer,
            {"/patients", "/appointments", "/sync/pull"},
        ),
        (
            UserRole.clinician,
            {"/patients", "/appointments", "/consultations", "/prescriptions", "/sync/pull"},
        ),
        (
            UserRole.pharmacist,
            {"/prescriptions", "/drug-stock", "/sync/pull"},
        ),
        (
            UserRole.administrator,
            {
                "/patients",
                "/appointments",
                "/consultations",
                "/prescriptions",
                "/drug-stock",
                "/users",
                "/reports",
                "/sync/pull",
            },
        ),
    ],
)
def test_role_access_matrix(client: TestClient, with_role, role: UserRole, allowed: set[str]) -> None:
    with_role(role)
    paths = (
        "/patients",
        "/appointments",
        "/consultations",
        "/prescriptions",
        "/drug-stock",
        "/users",
        "/reports",
        "/sync/pull",
    )
    for path in paths:
        expected = 200 if path in allowed else 403
        assert client.get(f"/api/v1{path}").status_code == expected, f"{role.value} -> {path}"


def test_registration_creates_registry_officer(client: TestClient, sample_clinic) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice Banda",
            "username": "alice",
            "password": "securepass123",
            "clinic_id": sample_clinic.id,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == UserRole.registry_officer.value
    assert body["is_active"] is True
    assert "password_hash" not in body


def test_registration_cannot_assign_a_role(client: TestClient, sample_clinic) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Root User",
            "username": "root-attempt",
            "password": "securepass123",
            "clinic_id": sample_clinic.id,
            "role": UserRole.administrator.value,
        },
    )
    assert response.status_code == 422


def test_registration_rejects_duplicate_username(client: TestClient, sample_registry_officer: User) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Duplicate User",
            "username": sample_registry_officer.username,
            "password": "securepass123",
            "clinic_id": sample_registry_officer.clinic_id,
        },
    )
    assert response.status_code == 409


def test_registration_rejects_unknown_clinic(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "No Clinic",
            "username": "no-clinic",
            "password": "securepass123",
            "clinic_id": "missing-clinic-id",
        },
    )
    assert response.status_code == 404


def test_login_token_uses_configured_expiration(
    client: TestClient, sample_registry_officer: User
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": sample_registry_officer.username, "password": "password123"},
    )
    assert response.status_code == 200

    claims = jwt.decode(
        response.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    expires_at = datetime.fromtimestamp(claims["exp"], timezone.utc)
    remaining = expires_at - datetime.now(timezone.utc)
    assert timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) - timedelta(seconds=5) <= remaining
    assert remaining <= timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def test_admin_cannot_demote_or_deactivate_self(admin_client: TestClient, sample_admin: User) -> None:
    role_response = admin_client.patch(
        f"/api/v1/users/{sample_admin.id}",
        json={"role": UserRole.clinician.value},
    )
    deactivate_response = admin_client.patch(
        f"/api/v1/users/{sample_admin.id}",
        json={"is_active": False},
    )
    delete_response = admin_client.delete(f"/api/v1/users/{sample_admin.id}")
    assert role_response.status_code == 400
    assert deactivate_response.status_code == 400
    assert delete_response.status_code == 400


def test_admin_can_update_another_user(admin_client: TestClient, sample_registry_officer: User) -> None:
    response = admin_client.patch(
        f"/api/v1/users/{sample_registry_officer.id}",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_pharmacist_sync_does_not_receive_patient_records(
    client: TestClient, with_role, sample_patient
) -> None:
    with_role(UserRole.pharmacist)
    response = client.get("/api/v1/sync/pull")
    assert response.status_code == 200
    body = response.json()
    assert body["patients"] == []
    assert body["consultations"] == []
    assert body["appointments"] == []
    assert body["drug_stock"] == []


def test_registry_officer_cannot_push_drug_stock(
    client: TestClient, with_role
) -> None:
    with_role(UserRole.registry_officer)
    response = client.post(
        "/api/v1/sync/push",
        json={
            "device_id": "device-1",
            "items": [
                {
                    "entity_type": "drug_stock",
                    "data": {
                        "clinic_id": "clinic-id",
                        "drug_name": "Paracetamol",
                        "quantity_available": 10,
                    },
                }
            ],
        },
    )
    assert response.status_code == 403
