"""Password hashing and JWT helpers.

Hashing uses the ``bcrypt`` library directly. ``passlib`` is deliberately not
used: passlib 1.7.x cannot initialise its bcrypt backend against bcrypt 5.x
(its capability probe feeds bcrypt a >72 byte secret, which bcrypt now
rejects), so calling it blows up before it ever hashes anything.

bcrypt only considers the first 72 bytes of a password, so input is truncated
to that length explicitly rather than letting the library raise.
"""

from datetime import datetime, timedelta, timezone
import hashlib

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    """Encode a password to the bytes bcrypt will hash (max 72 bytes)."""
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Backward-compatible alias for the application's bcrypt hasher."""
    return get_password_hash(password)


def get_password_hash(password: str) -> str:
    """Return the bcrypt hash of ``password`` as a UTF-8 string."""
    hashed = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")

# Alias kept because the test fixtures import this name.
hash_password = get_password_hash

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` when ``plain_password`` matches ``hashed_password``."""
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # A malformed stored hash should read as "no match", not a 500.
        return False


def create_access_token(
    subject: str,
    extra_claims: dict | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Return a signed JWT containing the subject and optional extra claims."""
    to_encode = {"sub": subject, **(extra_claims or {})}

    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode ``token`` and return its claims.

    ``JWTError`` is allowed to propagate so FastAPI dependencies can convert
    it into the application's standard credentials error.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def verify_access_token(token: str) -> dict:
    """Decode ``token`` and raise ``401`` when it is invalid or expired."""
    try:
        return decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --------------------------------------------------------------------------
# Password reset tokens
# --------------------------------------------------------------------------

PASSWORD_RESET_PURPOSE = "password_reset"


def _password_fingerprint(password_hash: str) -> str:
    """Short digest of the stored hash, embedded in reset tokens.

    The fingerprint changes the moment the password does, so a reset token
    stops working as soon as it has been used (or the password has changed by
    any other route) without needing a token table. It is a one-way digest of
    a bcrypt hash, so it reveals nothing useful if the token is inspected.
    """
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def create_password_reset_token(user_id: str, password_hash: str) -> str:
    """Return a short-lived, single-use token that authorises one password reset."""
    return create_access_token(
        subject=user_id,
        extra_claims={"purpose": PASSWORD_RESET_PURPOSE, "fp": _password_fingerprint(password_hash)},
        expires_delta=timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )


def decode_password_reset_token(token: str) -> dict:
    """Decode a reset token; raises ``JWTError`` if invalid, expired or not a reset token."""
    claims = decode_access_token(token)
    if claims.get("purpose") != PASSWORD_RESET_PURPOSE or not claims.get("sub"):
        raise JWTError("Not a password reset token")
    return claims


def reset_token_matches_password(claims: dict, password_hash: str) -> bool:
    """True while the password has not changed since the token was issued."""
    return claims.get("fp") == _password_fingerprint(password_hash)
