"""Pydantic schemas for user accounts.

Split into the usual shapes: a write model for creation, a partial model for
updates, and a read model that never exposes the password hash. ``role`` is
typed as :class:`app.models.user.UserRole` so FastAPI validates and documents
the allowed values automatically.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole
from app.schemas.base import SyncMetadataOut

_MAX_PASSWORD_BYTES = 72


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=3, max_length=100)
    role: UserRole = UserRole.registry_officer
    clinic_id: str


class UserCreate(UserBase):
    id: str | None = None
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        """
        Reject (rather than silently truncate) passwords bcrypt can't hash
        in full. See app/core/security.py for why this matters.
        """
        if len(value.encode("utf-8")) > _MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {_MAX_PASSWORD_BYTES} bytes.")
        return value


class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=3, max_length=100)
    clinic_id: str
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > _MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {_MAX_PASSWORD_BYTES} bytes.")
        return value


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(UserBase, SyncMetadataOut):
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str