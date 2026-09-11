"""User account model.

A user has exactly one role (see :class:`app.models.enums.UserRole`) which is
what role based access control keys off. The ``role`` column stores the *value*
of the enum (``"admin"`` / ``"user"``) rather than the member name, so the
database stays readable and remains stable if the enum members are ever
renamed.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Enum, String, TIMESTAMP, Uuid, true

from app.core.database import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, index=True, nullable=False, default=uuid.uuid4)
    username = Column(String, unique=False, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, default=datetime.utcnow)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def has_role(self, *roles: UserRole) -> bool:
        """Return ``True`` when this user holds any of ``roles``.

        Reads as intent (``if user.has_role(...)``) instead of forcing call
        sites to reach into the raw column value.
        """
        return self.role in roles
