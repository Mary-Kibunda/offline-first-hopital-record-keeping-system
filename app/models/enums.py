"""Enumerations shared across the application.

Kept in one module so the closed sets of values the system validates against
have a single source of truth. The first (and currently only) entry is the set
of roles used for role based access control.
"""

from enum import Enum


class UserRole(str, Enum):
    """The roles a user account can hold.

    ``ADMIN`` can manage user accounts and view hospital wide reports.
    ``USER`` is the default clinical/records role and is limited to the
    standard day to day data operations.
    """

    ADMIN = "admin"
    USER = "user"

    @classmethod
    def values(cls) -> list[str]:
        """Return the raw string values of every role.

        Handy for building validators, SQLAlchemy ``values_callable`` hooks and
        documentation, without callers repeating the list.
        """
        return [role.value for role in cls]
