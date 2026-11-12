"""Create the documented local-development clinic and sample accounts."""

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.clinic import Clinic
from app.models.user import User, UserRole

SAMPLE_USERS = (
    ("Ruth Mwape", "r.mwape", UserRole.administrator, "adminpass123"),
    ("Mutinta Banda", "m.banda", UserRole.registry_officer, "password123"),
    ("Chanda Phiri", "c.phiri", UserRole.clinician, "password123"),
    ("Temwani Zulu", "t.zulu", UserRole.pharmacist, "password123"),
)


def seed(db: Session) -> None:
    clinic = db.query(Clinic).filter(Clinic.name == "Chongwe First-Level Hospital").first()
    if clinic is None:
        clinic = Clinic(name="Chongwe First-Level Hospital", location="Chongwe")
        db.add(clinic)
        db.flush()

    for name, username, role, password in SAMPLE_USERS:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            db.add(
                User(
                    name=name,
                    username=username,
                    role=role,
                    clinic_id=clinic.id,
                    password_hash=get_password_hash(password),
                )
            )
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed(db)
    print("Sample clinic and accounts are ready.")


if __name__ == "__main__":
    main()
