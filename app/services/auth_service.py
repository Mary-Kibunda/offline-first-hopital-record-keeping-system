"""Authentication service.

Owns the queries and password work needed to log a user in and register a new
account. Password hashing and verification are delegated to
:mod:`app.core.security` - the same module the token helpers live in - so there
is exactly one implementation of each.
"""

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """
    Return the matching active user if the username/password are correct,
    otherwise None. Deliberately returns None rather than raising for a bad
    password vs. a missing user — the API layer treats both the same way
    (a generic "incorrect username or password") so as not to leak which
    part was wrong.
    """
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
