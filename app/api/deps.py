"""Shared FastAPI dependencies.

Two jobs live here:

1. Resolving the calling user from the bearer token (``get_current_user`` and
   ``get_current_active_user``).
2. Role based access control - ``require_admin`` and the ``require_roles``
   factory that build on the resolved user and raise ``403`` when the role is
   not permitted.

Routes enforce a policy either by adding the guard to
``APIRouter(dependencies=[...])`` (whole router) or by declaring it as a
parameter (when they also need the user object).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_access_token
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import AuthService

security = HTTPBearer()

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer token and load the matching user.

    Raises ``401`` when the token is missing, invalid or unknown, and ``403``
    when the account exists but has been deactivated.
    """
    payload = verify_access_token(credentials.credentials)
    if not payload:
        raise INVALID_CREDENTIALS

    email = payload.get("sub")
    if not email:
        raise INVALID_CREDENTIALS

    user = AuthService.get_user_by_email(db, email)
    if user is None:
        raise INVALID_CREDENTIALS

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Thin alias kept for readability at call sites."""
    return current_user


def require_roles(*allowed_roles: UserRole):
    """Build a dependency that only lets ``allowed_roles`` through.

    Returning a *factory* rather than one function per role combination keeps
    the policy readable - ``require_roles(UserRole.ADMIN)`` - and avoids a
    proliferation of near identical guards.
    """
    allowed = frozenset(allowed_roles)

    async def role_guard(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_guard


#: Guard for endpoints restricted to administrators.
require_admin = require_roles(UserRole.ADMIN)

#: Guard for endpoints open to any signed-in user (admin or standard).
require_any_role = require_roles(UserRole.ADMIN, UserRole.USER)
