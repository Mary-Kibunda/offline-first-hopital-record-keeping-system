"""User management service used by the admin-only endpoints.

Kept separate from :mod:`app.services.auth_service` because the concerns are
different: authentication answers "can this person log in", user management is
"an admin administering accounts". Every query here assumes the caller has
already been authorised by the role guards in :mod:`app.api.deps`.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserUpdate

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


class UserService:

    @staticmethod
    def list_users(
        db: Session,
        skip: int = 0,
        limit: int = DEFAULT_PAGE_SIZE,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> list[User]:
        """Return users, optionally filtered by role and/or active state."""
        query = db.query(User)
        if role is not None:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_user(db: Session, user_id: UUID) -> Optional[User]:
        """Return the user with ``user_id`` or ``None``."""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_user(db: Session, user: User, data: UserUpdate) -> User:
        """Apply the provided fields to ``user`` and return it.

        Only fields the caller actually sent are touched (``exclude_unset``),
        so a partial update never blanks out columns it did not mention. A
        supplied password is hashed before storage.
        """
        payload = data.model_dump(exclude_unset=True)
        password = payload.pop("password", None)
        if password:
            user.hashed_password = get_password_hash(password)
        for field, value in payload.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def set_role(db: Session, user: User, role: UserRole) -> User:
        """Assign ``role`` to ``user``."""
        user.role = role
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def set_active(db: Session, user: User, is_active: bool) -> User:
        """Activate or deactivate ``user``."""
        user.is_active = is_active
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user: User) -> None:
        """Permanently remove ``user``."""
        db.delete(user)
        db.commit()
