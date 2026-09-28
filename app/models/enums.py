"""Enumerations shared across the application.

Kept in one module so the closed sets of values the system validates against
have a single source of truth.
"""

from enum import Enum


class UserRole(str, Enum):
    """The roles a user account can hold."""

    ADMIN = "admin"
    USER = "user"

    @classmethod
    def values(cls) -> list[str]:
        """Return the raw string values of every role."""
        return [role.value for role in cls]


class HospitalType(str, Enum):
    """The type of care facility represented by a hospital record."""

    GENERAL = "general"
    SPECIALTY = "specialty"
    CLINIC = "clinic"
    TEACHING = "teaching"

    @classmethod
    def values(cls) -> list[str]:
        return [entry.value for entry in cls]


class Gender(str, Enum):
    """Supported patient gender values."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

    @classmethod
    def values(cls) -> list[str]:
        return [entry.value for entry in cls]


class AppointmentStatus(str, Enum):
    """Lifecycle states for appointments."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

    @classmethod
    def values(cls) -> list[str]:
        return [entry.value for entry in cls]

