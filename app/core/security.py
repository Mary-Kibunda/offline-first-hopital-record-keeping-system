"""Password hashing and JWT helpers.

Hashing uses the ``bcrypt`` library directly. ``passlib`` is deliberately not
used: passlib 1.7.x cannot initialise its bcrypt backend against bcrypt 5.x
(its capability probe feeds bcrypt a >72 byte secret, which bcrypt now
rejects), so calling it blows up before it ever hashes anything.

bcrypt only considers the first 72 bytes of a password, so input is truncated
to that length explicitly rather than letting the library raise.
"""

from datetime import datetime, timedelta

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    """Encode a password to the bytes bcrypt will hash (max 72 bytes)."""
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    """Return the bcrypt hash of ``password`` as a UTF-8 string."""
    hashed = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` when ``plain_password`` matches ``hashed_password``."""
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # A malformed stored hash should read as "no match", not a 500.
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Return a signed JWT containing ``data`` plus an expiry claim."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_access_token(token: str) -> dict:
    """Decode ``token`` and return its claims.

    Raises ``401`` for any invalid or expired token. ``JWTError`` is the base
    class of every python-jose JWT failure, so one handler covers them all.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
