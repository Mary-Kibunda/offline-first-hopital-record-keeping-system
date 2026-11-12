"""Authentication endpoints.

Public surface:

* ``POST /auth/register`` - self-service sign up. Always creates a
  ``registry_officer`` account; a caller cannot choose a privileged role.
* ``POST /auth/login``    - OAuth2 password flow, returns a bearer token.
* ``GET  /auth/me``       - the current user, useful as a token sanity check.
* ``POST /auth/forgot-password`` - emails a time-limited reset link to the address.
* ``POST /auth/reset-password``  - sets a new password from that link's token.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import logging
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    get_password_hash,
    reset_token_matches_password,
)
from app.models.user import User
from app.schemas.user import ForgotPasswordRequest, MessageResponse, ResetPasswordRequest, Token, UserRead
from app.services.auth_service import authenticate_user
from app.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)

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



_FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, a password reset link has been sent."
_INVALID_RESET_TOKEN = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="This reset link is invalid or has expired. Please request a new one.",
)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Email a reset link to the address on file.

    The response is identical whether or not the address belongs to an
    account, so this endpoint cannot be used to discover who has one. The
    link goes only to the account's own inbox - that is what proves the
    requester controls it.
    """
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is not None and user.is_active:
        token = create_password_reset_token(user.id, user.password_hash)
        background_tasks.add_task(send_password_reset_email, user.email, user.name, token)
    return MessageResponse(detail=_FORGOT_PASSWORD_MESSAGE)

@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Set a new password using the token from the emailed link (single use)."""
    try:
        claims = decode_password_reset_token(payload.token)
    except JWTError:
        raise _INVALID_RESET_TOKEN

    user = db.get(User, claims["sub"])
    if user is None or not user.is_active or not reset_token_matches_password(claims, user.password_hash):
        raise _INVALID_RESET_TOKEN

    user.password_hash = get_password_hash(payload.new_password)
    user.version += 1
    db.commit()
    return MessageResponse(detail="Your password has been reset. You can now sign in.")



