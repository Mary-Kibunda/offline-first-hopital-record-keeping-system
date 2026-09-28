"""User account model.

A user has exactly one role (see :class:`app.models.enums.UserRole`) which is
what role based access control keys off. The ``role`` column stores the *value*
of the enum (``"admin"`` / ``"user"``) rather than the member name, so the
database stays readable and remains stable if the enum members are ever
renamed.
"""

import enum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin


class UserRole(str, enum.Enum):
    registry_officer = "registry_officer"
    clinician = "clinician"
    pharmacist = "pharmacist"
    administrator = "administrator"


class User(Base, SyncMixin):
    __tablename__ = "users"

    clinic_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinics.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        nullable=False,
        default=UserRole.registry_officer,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="users")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="staff")
    consultations: Mapped[list["Consultation"]] = relationship(back_populates="staff")
