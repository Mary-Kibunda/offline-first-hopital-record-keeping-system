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

"""
Shared FastAPI dependencies: pulling the current user out of a bearer
token, and restricting endpoints to specific roles.
"""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Decode the bearer token, look up the user it identifies, and reject the
    request if the token is invalid/expired or the user no longer exists or
    has been deactivated.
    """
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise _CREDENTIALS_ERROR from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise _CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """
    Dependency factory for role-gated endpoints, e.g.:

        @router.get("/", dependencies=[Depends(require_roles(UserRole.administrator))])

    or, to also get the resolved user object in the handler:

        current_user: User = Depends(require_roles(UserRole.administrator))
    """

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return _check


require_admin = require_roles(UserRole.administrator)
