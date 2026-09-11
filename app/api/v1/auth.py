"""Authentication endpoints.

Public surface:

* ``POST /auth/register`` - self-service sign up. Always creates a standard
  ``user`` account; a caller cannot promote themselves to admin here.
* ``POST /auth/login``    - OAuth2 password flow, returns a bearer token.
* ``GET  /auth/me``       - the current user, useful as a token sanity check.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Register a new standard user account."""
    if AuthService.is_email_taken(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return AuthService.create_user(db, payload, role=UserRole.USER)


@router.post("/login", response_model=Token)
def user_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate and return a bearer token.

    ``OAuth2PasswordRequestForm`` only exposes ``username``; the client is
    expected to send the account email in that field.
    """
    user = AuthService.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value},
        expires_delta=access_token_expires,
    )

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Return the authenticated user's profile."""
    return current_user
