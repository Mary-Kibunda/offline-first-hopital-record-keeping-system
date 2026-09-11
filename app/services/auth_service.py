"""Authentication service.

Owns the queries and password work needed to log a user in and register a new
account. Password hashing and verification are delegated to
:mod:`app.core.security` - the same module the token helpers live in - so there
is exactly one implementation of each.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate


class AuthService:

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Return the user with ``email`` or ``None``."""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """Return the user when ``password`` matches, otherwise ``None``.

        Deliberately does not reveal whether the email or the password was
        wrong - both cases return ``None``.
        """
        user = AuthService.get_user_by_email(db, email)
        if user is None:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_user(
        db: Session,
        user_create: UserCreate,
        role: Optional[UserRole] = None,
    ) -> User:
        """Persist a new user and return it.

        ``role`` overrides whatever the payload carried, which lets the public
        registration endpoint force a standard ``user`` role while the admin
        endpoint passes an explicitly chosen one.
        """
        resolved_role = role or user_create.role or UserRole.USER
        db_user = User(
            email=user_create.email,
            username=user_create.username,
            hashed_password=get_password_hash(user_create.password),
            role=resolved_role,
            is_active=True,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def is_email_taken(db: Session, email: str) -> bool:
        """Return ``True`` when an account already uses ``email``."""
        return db.query(User).filter(User.email == email).first() is not None
