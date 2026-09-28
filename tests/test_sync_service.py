"""Tests for :class:`app.services.sync_service.SyncService`.

These drive the sync helpers directly against the shared in-memory SQLite
session from ``conftest`` so the conflict resolution, merge and validation
paths are exercised without going through HTTP.

The ``User`` model is used as a convenient real ORM model - the service is
generic over the model class, so any persisted table would do.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.enums import UserRole
from app.models.user import User
from app.services.sync_service import SyncService, _parse_timestamp


def _payload(db_session, email: str, password: str = "hash", **overrides) -> dict:
    """Insert a user directly and return a sync-style payload for it."""
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=password,
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "role": UserRole.USER,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# _parse_timestamp
# --------------------------------------------------------------------------

@pytest.mark.parametrize("missing", [None])
def test_parse_timestamp_returns_aware_min_for_none(missing):
    parsed = _parse_timestamp(missing)
    assert parsed.tzinfo is not None
    assert parsed == datetime.min.replace(tzinfo=timezone.utc)


def test_parse_timestamp_normalises_naive_and_aware():
    naive = datetime(2024, 1, 1, 12, 0, 0)
    aware = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert _parse_timestamp(naive) == _parse_timestamp(aware)


def test_parse_timestamp_reads_iso_strings():
    assert _parse_timestamp("2024-01-01T12:00:00") == _parse_timestamp(
        datetime(2024, 1, 1, 12, 0, 0)
    )


def test_parse_timestamp_falls_back_on_garbage():
    assert _parse_timestamp("not-a-date") == datetime.min.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# _upsert_record
# --------------------------------------------------------------------------

def test_upsert_record_inserts_new_row(db_session):
    payload = {
        "id": None,
        "email": "new@example.com",
        "username": "new",
        "hashed_password": "hash",
        "role": UserRole.USER,
        "is_active": True,
    }
    import uuid

    payload["id"] = uuid.uuid4()

    SyncService._upsert_record(db_session, User, payload)
    db_session.commit()

    stored = db_session.query(User).filter_by(email="new@example.com").first()
    assert stored is not None
    assert stored.username == "new"


def test_upsert_record_updates_existing_row(db_session):
    payload = _payload(db_session, "update@example.com")
    payload["username"] = "renamed"

    SyncService._upsert_record(db_session, User, payload)
    db_session.commit()

    stored = db_session.query(User).filter_by(id=payload["id"]).one()
    assert stored.username == "renamed"


def test_upsert_record_rejects_missing_id(db_session):
    with pytest.raises(ValueError):
        SyncService._upsert_record(db_session, User, {"email": "nobody@example.com"})


def test_upsert_record_rejects_none_id(db_session):
    with pytest.raises(ValueError):
        SyncService._upsert_record(
            db_session, User, {"id": None, "email": "nobody@example.com"}
        )


# --------------------------------------------------------------------------
# _resolve_conflict
# --------------------------------------------------------------------------

def test_resolve_conflict_prefers_newer_local(db_session):
    payload = _payload(db_session, "conflict@example.com")
    now = datetime.now(timezone.utc)

    local = {**payload, "username": "local-wins", "updated_at": now}
    remote = {**payload, "username": "remote", "updated_at": now - timedelta(hours=1)}

    SyncService._resolve_conflict(db_session, User, local, remote)
    db_session.commit()

    stored = db_session.query(User).filter_by(id=payload["id"]).one()
    assert stored.username == "local-wins"


def test_resolve_conflict_prefers_newer_remote(db_session):
    payload = _payload(db_session, "conflict2@example.com")
    now = datetime.now(timezone.utc)

    local = {**payload, "username": "local", "updated_at": now - timedelta(hours=1)}
    remote = {**payload, "username": "remote-wins", "updated_at": now}

    SyncService._resolve_conflict(db_session, User, local, remote)
    db_session.commit()

    stored = db_session.query(User).filter_by(id=payload["id"]).one()
    assert stored.username == "remote-wins"


def test_resolve_conflict_handles_mixed_naive_and_aware(db_session):
    """A naive datetime on one side must not raise against an aware one."""
    payload = _payload(db_session, "mixed@example.com")

    local = {**payload, "username": "local", "updated_at": datetime.utcnow()}
    remote = {
        **payload,
        "username": "remote",
        "updated_at": datetime.now(timezone.utc) - timedelta(days=1),
    }

    # Should not raise; local is newer once both are normalised to UTC-aware.
    SyncService._resolve_conflict(db_session, User, local, remote)
    db_session.commit()

    stored = db_session.query(User).filter_by(id=payload["id"]).one()
    assert stored.username == "local"


def test_resolve_conflict_defaults_missing_timestamp(db_session):
    payload = _payload(db_session, "default@example.com")

    local = {**payload, "username": "local-kept"}
    remote = {**payload, "username": "remote-kept"}

    # Both timestamps are absent -> equal -> remote wins (else branch).
    SyncService._resolve_conflict(db_session, User, local, remote)
    db_session.commit()

    stored = db_session.query(User).filter_by(id=payload["id"]).one()
    assert stored.username == "remote-kept"


# --------------------------------------------------------------------------
# handle_conflict / merge_data
# --------------------------------------------------------------------------

def test_handle_conflict_applies_local_changes(db_session):
    payload = _payload(db_session, "handle@example.com")
    now = datetime.now(timezone.utc)

    local = [{**payload, "is_active": False, "updated_at": now}]
    remote = [{**payload, "is_active": True, "updated_at": now - timedelta(hours=1)}]

    SyncService.handle_conflict(db_session, User, local, remote)

    stored = db_session.query(User).filter_by(id=payload["id"]).one()
    assert stored.is_active is False


def test_handle_conflict_inserts_when_no_remote_copy(db_session):
    import uuid

    payload = {
        "id": uuid.uuid4(),
        "email": "no-remote@example.com",
        "username": "no-remote",
        "hashed_password": "hash",
        "role": UserRole.USER,
        "is_active": True,
    }

    SyncService.handle_conflict(db_session, User, [payload], [])

    stored = db_session.query(User).filter_by(email="no-remote@example.com").first()
    assert stored is not None


def test_merge_data_adds_remote_only_records(db_session):
    import uuid

    local_payload = _payload(db_session, "local-only@example.com")
    remote_only = {
        "id": uuid.uuid4(),
        "email": "remote-only@example.com",
        "username": "remote-only",
        "hashed_password": "hash",
        "role": UserRole.USER,
        "is_active": True,
    }

    SyncService.merge_data(db_session, User, [local_payload], [remote_only])

    assert db_session.query(User).filter_by(email="remote-only@example.com").first()
    assert db_session.query(User).filter_by(email="local-only@example.com").first()


def test_merge_data_is_idempotent(db_session):
    payload = _payload(db_session, "idempotent@example.com")

    SyncService.merge_data(db_session, User, [payload], [payload])
    SyncService.merge_data(db_session, User, [payload], [payload])

    assert db_session.query(User).filter_by(id=payload["id"]).count() == 1


def test_merge_data_rolls_back_and_reraises_on_failure(db_session):
    # A payload with a completely unknown column should blow up inside the ORM
    # and leave the session clean rather than poisoned.
    import uuid

    bad = {
        "id": uuid.uuid4(),
        "email": "bad@example.com",
        "username": "bad",
        "hashed_password": "hash",
        "role": UserRole.USER,
        "is_active": True,
        "does_not_exist": 1,
    }

    with pytest.raises(Exception):
        SyncService.merge_data(db_session, User, [bad], [])

    # The session must still be usable for a follow-up query.
    assert db_session.query(User).count() >= 0
