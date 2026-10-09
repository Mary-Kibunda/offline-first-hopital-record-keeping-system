from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.main import app
from app.models.clinic import Clinic
from app.models.sync_log import SyncLog, SyncOperation
from app.models.user import User, UserRole


def _add_user(
    db_session: Session, clinic: Clinic, username: str, role: UserRole
) -> User:
    user = User(
        name=username,
        username=username,
        password_hash="test-password-hash",
        role=role,
        clinic_id=clinic.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _add_sync_log(db_session: Session, user_id: str | None, entity_id: str) -> None:
    db_session.add(
        SyncLog(
            user_id=user_id,
            device_id=f"device-{entity_id}",
            entity_type="patient",
            entity_id=entity_id,
            operation=SyncOperation.create,
            conflict_detected=False,
            conflict_resolved=True,
            synced_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()


def test_staff_sync_log_only_contains_their_records(
    client: TestClient,
    db_session: Session,
    sample_clinic: Clinic,
) -> None:
    staff = _add_user(
        db_session, sample_clinic, "sync-staff", UserRole.registry_officer
    )
    admin = _add_user(
        db_session, sample_clinic, "sync-admin", UserRole.administrator
    )
    _add_sync_log(db_session, staff.id, "staff-record")
    _add_sync_log(db_session, admin.id, "admin-record")
    _add_sync_log(db_session, None, "legacy-record")

    app.dependency_overrides[get_current_user] = lambda: staff
    try:
        response = client.get("/api/v1/sync/log")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert [entry["entity_id"] for entry in response.json()] == ["staff-record"]


def test_admin_sync_log_contains_all_users_records(
    client: TestClient,
    db_session: Session,
    sample_clinic: Clinic,
) -> None:
    staff = _add_user(
        db_session, sample_clinic, "sync-staff", UserRole.registry_officer
    )
    admin = _add_user(
        db_session, sample_clinic, "sync-admin", UserRole.administrator
    )
    _add_sync_log(db_session, staff.id, "staff-record")
    _add_sync_log(db_session, admin.id, "admin-record")
    _add_sync_log(db_session, None, "legacy-record")

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.get("/api/v1/sync/log")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    records = {entry["entity_id"]: entry for entry in response.json()}
    assert {"staff-record", "admin-record", "legacy-record"} <= set(records)
    assert records["staff-record"]["user_name"] == staff.name
    assert records["admin-record"]["user_name"] == admin.name
    assert records["legacy-record"]["user_name"] is None


def test_sync_push_attributes_log_to_authenticated_user(
    client: TestClient,
    db_session: Session,
    sample_clinic: Clinic,
) -> None:
    staff = _add_user(
        db_session, sample_clinic, "sync-staff", UserRole.registry_officer
    )
    entity_id = str(uuid4())
    app.dependency_overrides[get_current_user] = lambda: staff
    try:
        response = client.post(
            "/api/v1/sync/push",
            json={
                "device_id": "staff-device",
                "items": [
                    {
                        "entity_type": "patient",
                        "data": {
                            "id": entity_id,
                            "version": 1,
                            "origin_device_id": "staff-device",
                            "first_name": "Test",
                            "last_name": "Patient",
                            "date_of_birth": "2000-01-01",
                            "gender": "female",
                            "registered_clinic_id": sample_clinic.id,
                        },
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    log_entry = db_session.query(SyncLog).filter_by(entity_id=entity_id).one()
    assert log_entry.user_id == staff.id
