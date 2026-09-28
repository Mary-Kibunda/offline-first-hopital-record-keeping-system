from fastapi.testclient import TestClient

from app.models.user import User


def test_login_succeeds_with_correct_credentials(client: TestClient, sample_registry_officer: User) -> None:
    response = client.post(
        "/api/v1/auth/login", data={"username": "m.banda", "password": "password123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0


def test_login_fails_with_wrong_password(client: TestClient, sample_registry_officer: User) -> None:
    response = client.post(
        "/api/v1/auth/login", data={"username": "m.banda", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_login_fails_for_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", data={"username": "does.not.exist", "password": "whatever123"}
    )
    assert response.status_code == 401


def test_me_returns_current_user(auth_client: TestClient, sample_registry_officer: User) -> None:
    response = auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "m.banda"


def test_protected_endpoint_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/patients")
    assert response.status_code == 401