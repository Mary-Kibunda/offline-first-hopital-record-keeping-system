"""Create the first administrator account (bootstrap script).

There is a chicken-and-egg problem with the very first account: the whole
``/users`` router is gated behind ``require_roles(UserRole.administrator)`` and
there is no self-service registration endpoint, so no admin can exist until one
is inserted out of band. This script does exactly that, using the same session
factory and password hashing helpers the application itself uses so the stored
hash can never drift from what ``/auth/login`` expects.

It is idempotent: running it again when the admin already exists is a no-op, so
it is safe to leave in the repo and re-run.

Usage (from the project root)::

    python -m app.scripts.seed_admin

Credentials can be overridden with environment variables; the defaults are
intended for local testing only.
"""

import os

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.clinic import Clinic
from app.models.user import User, UserRole

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "ChangeMe123!"
DEFAULT_NAME = "System Administrator"
DEFAULT_CLINIC_NAME = "Chairo Clinic"
DEFAULT_CLINIC_LOCATION = "Chongwe"


def seed_admin() -> None:
    """Create a clinic (if none exists) and the first administrator."""
    username = os.environ.get("SEED_ADMIN_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("SEED_ADMIN_PASSWORD", DEFAULT_PASSWORD)
    name = os.environ.get("SEED_ADMIN_NAME", DEFAULT_NAME)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing is not None:
            print(f"Admin '{username}' already exists (id={existing.id}) — nothing to do.")
            return

        # users.clinic_id is a non-nullable FK, so a clinic must exist first.
        # Reuse an existing clinic rather than creating a duplicate.
        clinic = db.query(Clinic).first()
        if clinic is None:
            clinic = Clinic(
                name=os.environ.get("SEED_CLINIC_NAME", DEFAULT_CLINIC_NAME),
                location=os.environ.get("SEED_CLINIC_LOCATION", DEFAULT_CLINIC_LOCATION),
            )
            db.add(clinic)
            db.flush()  # populate clinic.id before we reference it below
            print(f"Created clinic '{clinic.name}' (id={clinic.id}).")

        admin = User(
            name=name,
            username=username,
            password_hash=get_password_hash(password),
            role=UserRole.administrator,
            clinic_id=clinic.id,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"Created administrator '{username}' in clinic '{clinic.name}'.")
        print(f"Log in with username '{username}' and the password you configured.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
