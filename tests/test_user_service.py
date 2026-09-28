"""Tests for :class:`app.services.user_service.UserService`.

Covers the admin-only account flows: listing with filters, partial updates
(including the password-rehash path), role/active toggles and deletion.
"""

import pytest
from uuid import uuid4

from app.core.security import verify_password
from app.models.enums import UserRole
from app.schemas.user import UserUpdate
from app.services.user_service import UserService
from conftest import DEFAULT_PASSWORD, create_user


# --------------------------------------------------------------------------
# list_users / get_user
# --------------------------------------------------------------------------

def test_list_users_returns_all_by_default(db_session):
    create_user(db_session, "a@example.com")
    create_user(db_session, "b@example.com")

    users = UserService.list_users(db_session)
    assert len(users) == 2


def test_list_users_filters_by_role(db_session):
    create_user(db_session, "admin@example.com", role=UserRole.ADMIN)
    create_user(db_session, "user@example.com", role=UserRole.USER)

    admins = UserService.list_users(db_session, role=UserRole.ADMIN)
    assert len(admins) == 1
    assert admins[0].email == "admin@example.com"


def test_list_users_filters_by_active(db_session):
    create_user(db_session, "active@example.com", is_active=True)
    create_user(db_session, "inactive@example.com", is_active=False)

    inactive = UserService.list_users(db_session, is_active=False)
    assert len(inactive) == 1
    assert inactive[0].email == "inactive@example.com"


def test_list_users_respects_skip_and_limit(db_session):
    for i in range(5):
        create_user(db_session, f"user{i}@example.com")

    page = UserService.list_users(db_session, skip=1, limit=2)
    assert len(page) == 2


def test_get_user_returns_none_for_unknown_id(db_session):
    assert UserService.get_user(db_session, uuid4()) is None


def test_get_user_returns_matching_user(db_session):
    user = create_user(db_session, "fetch@example.com")
    assert UserService.get_user(db_session, user.id).email == "fetch@example.com"


# --------------------------------------------------------------------------
# update_user
# --------------------------------------------------------------------------

def test_update_user_applies_partial_fields(db_session):
    user = create_user(db_session, "partial@example.com")

    updated = UserService.update_user(db_session, user, UserUpdate(username="newname"))

    assert updated.username == "newname"
    # Untouched fields are preserved rather than blanked out.
    assert updated.email == "partial@example.com"


def test_update_user_does_not_blank_unsent_columns(db_session):
    user = create_user(db_session, "keep@example.com")
    original_hash = user.hashed_password

    updated = UserService.update_user(db_session, user, UserUpdate())

    assert updated.email == "keep@example.com"
    assert updated.hashed_password == original_hash


def test_update_user_hashes_new_password(db_session):
    user = create_user(db_session, "rehash@example.com")

    UserService.update_user(
        db_session, user, UserUpdate(password="brandnewpass123")
    )

    assert user.hashed_password != "brandnewpass123"
    assert verify_password("brandnewpass123", user.hashed_password)


def test_update_user_can_change_email(db_session):
    user = create_user(db_session, "old@example.com")

    updated = UserService.update_user(
        db_session, user, UserUpdate(email="new@example.com")
    )

    assert updated.email == "new@example.com"


# --------------------------------------------------------------------------
# set_role / set_active
# --------------------------------------------------------------------------

def test_set_role_promotes_user(db_session):
    user = create_user(db_session, "promote@example.com", role=UserRole.USER)

    updated = UserService.set_role(db_session, user, UserRole.ADMIN)

    assert updated.role == UserRole.ADMIN


def test_set_active_deactivates_user(db_session):
    user = create_user(db_session, "deactivate@example.com", is_active=True)

    updated = UserService.set_active(db_session, user, False)

    assert updated.is_active is False


def test_set_active_reactivates_user(db_session):
    user = create_user(db_session, "reactivate@example.com", is_active=False)

    updated = UserService.set_active(db_session, user, True)

    assert updated.is_active is True


# --------------------------------------------------------------------------
# delete_user
# --------------------------------------------------------------------------

def test_delete_user_removes_row(db_session):
    user = create_user(db_session, "delete@example.com")
    user_id = user.id

    UserService.delete_user(db_session, user)

    assert UserService.get_user(db_session, user_id) is None


def test_delete_user_leaves_other_users(db_session):
    doomed = create_user(db_session, "doomed@example.com")
    kept = create_user(db_session, "kept@example.com")

    UserService.delete_user(db_session, doomed)

    assert UserService.get_user(db_session, kept.id) is not None


def test_delete_user_then_commit_session_stays_usable(db_session):
    user = create_user(db_session, "cleanup@example.com")
    UserService.delete_user(db_session, user)

    # The session should still be healthy for further work.
    assert db_session.query(type(user)).count() == 0
