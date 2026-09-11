"""Admin-only user management endpoints.

Every route on this router is gated by ``require_admin`` as a router level
dependency, so the whole surface is protected by construction. The routes that
need the acting admin's identity redeclare ``Depends(require_admin)`` as a
parameter (FastAPI caches the result, so the guard still runs once).

Guard rails worth noting:

* an anonymous or standard ``user`` caller cannot reach any of this;
* an admin cannot remove their own admin role;
* an admin cannot deactivate or delete their own account.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserRead,
    UserRoleUpdate,
    UserStatusUpdate,
    UserUpdate,
)
from app.services.auth_service import AuthService
from app.services.user_service import MAX_PAGE_SIZE, UserService

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[UserRead])
def list_users(
    role: UserRole | None = None,
    is_active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> list[User]:
    """List users, optionally filtered by role and/or active state."""
    return UserService.list_users(db, skip=skip, limit=limit, role=role, is_active=is_active)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Create a user with an explicitly chosen role."""
    if AuthService.is_email_taken(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return AuthService.create_user(db, payload, role=payload.role)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    """Fetch a single user by id."""
    user = UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, payload: UserUpdate, db: Session = Depends(get_db)) -> User:
    """Update a user's email, username or password."""
    user = UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserService.update_user(db, user, payload)


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    """Promote or demote a user."""
    user = UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id and payload.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin role",
        )
    return UserService.set_role(db, user, payload.role)


@router.patch("/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    """Activate or deactivate a user."""
    user = UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )
    return UserService.set_active(db, user, payload.is_active)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Delete a user account."""
    user = UserService.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )
    UserService.delete_user(db, user)
