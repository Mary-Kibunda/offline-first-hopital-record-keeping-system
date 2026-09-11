"""Pydantic schemas for user accounts.

Split into the usual shapes: a write model for creation, a partial model for
updates, and a read model that never exposes the password hash. ``role`` is
typed as :class:`app.models.enums.UserRole` so FastAPI validates and documents
the allowed values automatically.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    """Payload for creating a user.

    ``role`` defaults to a standard user. Public self-registration never
    honours a caller supplied role - only the admin endpoints do.
    """

    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    """Partial update payload; every field is optional."""

    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRoleUpdate(BaseModel):
    """Payload for changing a user's role."""

    role: UserRole


class UserStatusUpdate(BaseModel):
    """Payload for activating or deactivating a user."""

    is_active: bool


class UserRead(UserBase):
    """Safe representation of a user returned to clients."""

    id: UUID
    role: UserRole
    is_active: bool
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: EmailStr | None = None
    role: UserRole | None = None
