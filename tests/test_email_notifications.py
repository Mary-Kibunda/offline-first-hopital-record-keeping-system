"""Welcome email on user creation, and the forgot/reset password flow."""

from urllib.parse import parse_qs, urlparse

import pytest

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.services import email_service


@pytest.fixture
def outbox(monkeypatch):
    """Capture emails instead of sending them."""
    sent: list[dict] = []

    def fake_send(to: str, subject: str, text_body: str) -> bool:
        sent.append({"to": to, "subject": subject, "body": text_body})
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send)
    return sent


def _new_user_payload(clinic_id: str, **overrides) -> dict:
    payload = {
        "name": "Chola Mumba",
        "username": "c.mumba",
        "email": "Chola@Example.com",
        "role": "clinician",
        "clinic_id": clinic_id,
        "password": "TempPass#2026",
    }
    payload.update(overrides)
    return payload


def _token_from(body: str) -> str:
    link = next(line for line in body.splitlines() if "token=" in line)
    return parse_qs(urlparse(link.strip()).query)["token"][0]


# ---- welcome email ---------------------------------------------------------

def test_create_user_emails_username_and_password(admin_client, sample_clinic, outbox):
    r = admin_client.post("/api/v1/users", json=_new_user_payload(sample_clinic.id))
    assert r.status_code == 201
    assert r.json()["email"] == "chola@example.com"  # normalised
    assert "password" not in r.json()

    assert len(outbox) == 1
    mail = outbox[0]
    assert mail["to"] == "chola@example.com"
    assert "c.mumba" in mail["body"]
    assert "TempPass#2026" in mail["body"]


def test_created_user_can_log_in_with_emailed_credentials(admin_client, sample_clinic, outbox):
    admin_client.post("/api/v1/users", json=_new_user_payload(sample_clinic.id))
    r = admin_client.post("/api/v1/auth/login", data={"username": "c.mumba", "password": "TempPass#2026"})
    assert r.status_code == 200


def test_create_user_requires_valid_email(admin_client, sample_clinic, outbox):
    bad = _new_user_payload(sample_clinic.id, email="not-an-email")
    assert admin_client.post("/api/v1/users", json=bad).status_code == 422
    missing = _new_user_payload(sample_clinic.id)
    del missing["email"]
    assert admin_client.post("/api/v1/users", json=missing).status_code == 422
    assert outbox == []


def test_duplicate_email_rejected_and_nothing_sent(admin_client, sample_clinic, outbox):
    admin_client.post("/api/v1/users", json=_new_user_payload(sample_clinic.id))
    outbox.clear()
    dup = _new_user_payload(sample_clinic.id, username="other.user", email="CHOLA@example.com")
    assert admin_client.post("/api/v1/users", json=dup).status_code == 409
    assert outbox == []


def test_smtp_failure_does_not_break_user_creation(admin_client, sample_clinic, monkeypatch):
    def boom(*a, **k):
        raise OSError("mail server down")

    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.invalid")
    monkeypatch.setattr(email_service.smtplib, "SMTP", boom)
    r = admin_client.post("/api/v1/users", json=_new_user_payload(sample_clinic.id))
    assert r.status_code == 201


# ---- forgot / reset --------------------------------------------------------

def _make_user_with_email(admin_client, clinic, outbox):
    admin_client.post("/api/v1/users", json=_new_user_payload(clinic.id))
    outbox.clear()


def test_forgot_password_sends_link_to_account_email(admin_client, sample_clinic, outbox):
    _make_user_with_email(admin_client, sample_clinic, outbox)
    r = admin_client.post("/api/v1/auth/forgot-password", json={"email": "chola@example.com"})
    assert r.status_code == 200
    assert len(outbox) == 1
    assert outbox[0]["to"] == "chola@example.com"
    assert "/reset-password?token=" in outbox[0]["body"]


def test_forgot_password_does_not_reveal_whether_account_exists(admin_client, sample_clinic, outbox):
    _make_user_with_email(admin_client, sample_clinic, outbox)
    known = admin_client.post("/api/v1/auth/forgot-password", json={"email": "chola@example.com"})
    unknown = admin_client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(outbox) == 1  # only the real account got mail


def test_forgot_password_skips_deactivated_users(admin_client, sample_clinic, db_session, outbox):
    _make_user_with_email(admin_client, sample_clinic, outbox)
    db_session.query(User).filter(User.username == "c.mumba").one().is_active = False
    db_session.flush()
    admin_client.post("/api/v1/auth/forgot-password", json={"email": "chola@example.com"})
    assert outbox == []


def test_full_reset_flow(admin_client, sample_clinic, outbox):
    _make_user_with_email(admin_client, sample_clinic, outbox)
    admin_client.post("/api/v1/auth/forgot-password", json={"email": "chola@example.com"})
    token = _token_from(outbox[0]["body"])

    r = admin_client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "BrandNew#Pass1"})
    assert r.status_code == 200

    login = lambda pw: admin_client.post("/api/v1/auth/login", data={"username": "c.mumba", "password": pw})
    assert login("BrandNew#Pass1").status_code == 200
    assert login("TempPass#2026").status_code == 401


def test_reset_token_is_single_use(admin_client, sample_clinic, outbox):
    _make_user_with_email(admin_client, sample_clinic, outbox)
    admin_client.post("/api/v1/auth/forgot-password", json={"email": "chola@example.com"})
    token = _token_from(outbox[0]["body"])
    body = {"token": token, "new_password": "BrandNew#Pass1"}
    assert admin_client.post("/api/v1/auth/reset-password", json=body).status_code == 200
    body["new_password"] = "Another#Pass22"
    assert admin_client.post("/api/v1/auth/reset-password", json=body).status_code == 400


def test_reset_rejects_garbage_expired_and_wrong_purpose_tokens(admin_client, sample_clinic, db_session, outbox):
    from datetime import timedelta

    _make_user_with_email(admin_client, sample_clinic, outbox)
    user = db_session.query(User).filter(User.username == "c.mumba").one()
    pw = "BrandNew#Pass1"
    reset = lambda t: admin_client.post("/api/v1/auth/reset-password", json={"token": t, "new_password": pw})

    assert reset("garbage").status_code == 400
    # an ordinary login token must not work as a reset token
    assert reset(create_access_token(subject=user.id)).status_code == 400
    # expired reset token
    from app.core.security import create_password_reset_token
    import app.core.security as sec
    expired = sec.create_access_token(
        subject=user.id,
        extra_claims={"purpose": "password_reset", "fp": sec._password_fingerprint(user.password_hash)},
        expires_delta=timedelta(minutes=-1),
    )
    assert reset(expired).status_code == 400
    assert verify_password("TempPass#2026", user.password_hash)  # untouched


def test_reset_token_cannot_be_used_to_authenticate(client, sample_admin):
    from app.core.security import create_password_reset_token

    token = create_password_reset_token(sample_admin.id, sample_admin.password_hash)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_reset_enforces_password_rules(admin_client, sample_clinic, outbox):
    _make_user_with_email(admin_client, sample_clinic, outbox)
    admin_client.post("/api/v1/auth/forgot-password", json={"email": "chola@example.com"})
    token = _token_from(outbox[0]["body"])
    r = admin_client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"})
    assert r.status_code == 422
