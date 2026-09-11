"""Role based access control tests.

These exercise the guards end to end through the HTTP layer: who can log in,
who can reach the admin surface, and the self-protection rules that stop an
admin locking themselves out.
"""

from app.models.enums import UserRole
from conftest import API, DEFAULT_PASSWORD, auth_headers, create_user


def test_public_registration_defaults_to_standard_user(client):
    """A caller cannot self-assign the admin role at registration."""
    response = client.post(
        f"{API}/auth/register",
        json={
            "email": "alice@example.com",
            "username": "alice",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "user"
    assert body["is_active"] is True


def test_registration_rejects_duplicate_email(client, db_session):
    create_user(db_session, "bob@example.com")
    response = client.post(
        f"{API}/auth/register",
        json={"email": "bob@example.com", "username": "bob", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 409


def test_login_and_me_round_trip(client, db_session):
    create_user(db_session, "carol@example.com")
    headers = auth_headers(client, "carol@example.com")
    response = client.get(f"{API}/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "carol@example.com"
    assert body["role"] == "user"


def test_login_with_wrong_password_is_rejected(client, db_session):
    create_user(db_session, "dave@example.com")
    response = client.post(
        f"{API}/auth/login",
        data={"username": "dave@example.com", "password": "totally-wrong"},
    )
    assert response.status_code == 401


def test_anonymous_cannot_list_users(client):
    response = client.get(f"{API}/users")
    assert response.status_code in (401, 403)


def test_standard_user_cannot_list_users(client, db_session):
    create_user(db_session, "erin@example.com")
    headers = auth_headers(client, "erin@example.com")
    response = client.get(f"{API}/users", headers=headers)
    assert response.status_code == 403


def test_standard_user_cannot_create_admin(client, db_session):
    create_user(db_session, "frank@example.com")
    headers = auth_headers(client, "frank@example.com")
    response = client.post(
        f"{API}/users",
        headers=headers,
        json={
            "email": "wannabe-admin@example.com",
            "username": "wannabe",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code == 403


def test_standard_user_cannot_reach_reports_surface(client, db_session):
    """Any admin-only path must reject a standard user, not just /users."""
    create_user(db_session, "george@example.com")
    headers = auth_headers(client, "george@example.com")
    response = client.get(f"{API}/users/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 403


def test_admin_can_list_users(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    create_user(db_session, "user1@example.com", role=UserRole.USER)
    headers = auth_headers(client, "root@example.com")
    response = client.get(f"{API}/users", headers=headers)
    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert {"root@example.com", "user1@example.com"} <= emails


def test_admin_can_filter_users_by_role(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    create_user(db_session, "plain@example.com", role=UserRole.USER)
    headers = auth_headers(client, "root@example.com")
    response = client.get(f"{API}/users", headers=headers, params={"role": "admin"})
    assert response.status_code == 200
    roles = {user["role"] for user in response.json()}
    assert roles == {"admin"}


def test_admin_can_create_user_with_explicit_role(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    headers = auth_headers(client, "root@example.com")
    response = client.post(
        f"{API}/users",
        headers=headers,
        json={
            "email": "newadmin@example.com",
            "username": "newadmin",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "admin"


def test_admin_can_promote_user_and_grant_access(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    target = create_user(db_session, "grace@example.com", role=UserRole.USER)
    admin_headers = auth_headers(client, "root@example.com")
    target_headers = auth_headers(client, "grace@example.com")

    assert client.get(f"{API}/users", headers=target_headers).status_code == 403

    response = client.patch(
        f"{API}/users/{target.id}/role",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "admin"

    assert client.get(f"{API}/users", headers=target_headers).status_code == 200


def test_admin_cannot_demote_self(client, db_session):
    admin = create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    headers = auth_headers(client, "root@example.com")
    response = client.patch(
        f"{API}/users/{admin.id}/role",
        headers=headers,
        json={"role": "user"},
    )
    assert response.status_code == 400


def test_deactivated_user_is_locked_out(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    target = create_user(db_session, "henry@example.com", role=UserRole.USER)
    admin_headers = auth_headers(client, "root@example.com")
    target_headers = auth_headers(client, "henry@example.com")

    response = client.patch(
        f"{API}/users/{target.id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # The already issued token is refused on the next request...
    assert client.get(f"{API}/auth/me", headers=target_headers).status_code == 403
    # ...and a fresh login is refused too.
    login_response = client.post(
        f"{API}/auth/login",
        data={"username": "henry@example.com", "password": DEFAULT_PASSWORD},
    )
    assert login_response.status_code == 403


def test_admin_cannot_deactivate_self(client, db_session):
    admin = create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    headers = auth_headers(client, "root@example.com")
    response = client.patch(
        f"{API}/users/{admin.id}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 400


def test_admin_can_delete_user(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    target = create_user(db_session, "ivy@example.com", role=UserRole.USER)
    headers = auth_headers(client, "root@example.com")

    assert client.delete(f"{API}/users/{target.id}", headers=headers).status_code == 204
    assert client.get(f"{API}/users/{target.id}", headers=headers).status_code == 404


def test_admin_cannot_delete_self(client, db_session):
    admin = create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    headers = auth_headers(client, "root@example.com")
    assert client.delete(f"{API}/users/{admin.id}", headers=headers).status_code == 400


def test_admin_can_change_user_password(client, db_session):
    create_user(db_session, "root@example.com", role=UserRole.ADMIN)
    target = create_user(db_session, "jill@example.com", role=UserRole.USER)
    headers = auth_headers(client, "root@example.com")

    response = client.patch(
        f"{API}/users/{target.id}",
        headers=headers,
        json={"password": "brandnewpass1"},
    )
    assert response.status_code == 200, response.text

    login_response = client.post(
        f"{API}/auth/login",
        data={"username": "jill@example.com", "password": "brandnewpass1"},
    )
    assert login_response.status_code == 200
