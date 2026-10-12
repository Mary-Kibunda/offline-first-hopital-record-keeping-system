"""Authentication endpoints.

Public surface:

* ``POST /auth/register`` - self-service sign up. Always creates a
  ``registry_officer`` account; a caller cannot choose a privileged role.
* ``POST /auth/login``    - OAuth2 password flow, returns a bearer token.
* ``GET  /auth/me``       - the current user, useful as a token sanity check.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from datetime import timedelta

from app.core.security import create_access_token, get_password_hash
from app.models.mixins import new_uuid
from app.models.user import User, UserRole
from app.schemas.user import Token, UserRead, UserRegister
from app.services.auth_service import authenticate_user
from app.services.references import MissingReferenceError, validate_references

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That username is already taken.")

    try:
        validate_references(db, User, {"clinic_id": payload.clinic_id})
    except MissingReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    user = User(
        id=new_uuid(),
        name=payload.name,
        username=payload.username,
        role=UserRole.registry_officer,
        clinic_id=payload.clinic_id,
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role.value, "clinic_id": user.clinic_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
