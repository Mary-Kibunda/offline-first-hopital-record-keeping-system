"""Admin-only user management endpoints.

Every route on this router is gated by ``require_admin`` as a router level
dependency, so the whole surface is protected by construction. The routes that
need the acting admin's identity redeclare ``Depends(require_admin)`` as a
parameter (FastAPI caches the result, so the guard still runs once).

Guard rails worth noting:

* only an administrator can reach any of this;
* an admin cannot remove their own admin role;
* an admin cannot deactivate or delete their own account.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.mixins import new_uuid
from app.models.user import User, UserRole
from app.services.email_service import send_welcome_email
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.references import MissingReferenceError, validate_references

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> User:
    """Create an account and email the new user their username and password."""
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That username is already taken.")
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email is already in use.")

    password_hash = get_password_hash(payload.password)

    user_id = payload.id or new_uuid()
    user = User(
        id=user_id,
        name=payload.name,
        username=payload.username,
        email=email,
        role=payload.role,
        clinic_id=payload.clinic_id,
        password_hash=password_hash,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Sent after the commit, in the background: the account exists regardless of
    # whether the mail server is reachable.
    background_tasks.add_task(send_welcome_email, email, user.name, user.username, payload.password)
    return user


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.name).all()


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: str, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("email") is not None:
        changes["email"] = changes["email"].lower()
        taken = db.query(User).filter(User.email == changes["email"], User.id != user.id).first()
        if taken is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email is already in use.")
    for key, value in changes.items():
        setattr(user, key, value)
    user.version += 1

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=UserRead)
def remove_user_access(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> User:
    """
    Removes a user's ability to log in without deleting their historical
    records (consultations/appointments they created stay exactly as they
    are — this is a soft deactivation, not a hard delete, matching what the
    confirmation dialog on the User Management screen tells the admin will
    happen).
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    user.is_active = False
    user.version += 1
    db.commit()
    db.refresh(user)
    return user