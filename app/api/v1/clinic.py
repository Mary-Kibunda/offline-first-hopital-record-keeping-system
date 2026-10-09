from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.clinic import Clinic
from app.models.mixins import new_uuid
from app.models.user import User, UserRole
from app.schemas.clinic import ClinicCreate, ClinicRead

router = APIRouter(prefix="/clinics", tags=["clinics"])


@router.post(
    "",
    response_model=ClinicRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.administrator))],
)
def create_clinic(payload: ClinicCreate, db: Session = Depends(get_db)) -> Clinic:
    clinic_id = payload.id or new_uuid()
    if db.get(Clinic, clinic_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A clinic with this id already exists.")

    clinic = Clinic(id=clinic_id, **payload.model_dump(exclude={"id"}))
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.get("", response_model=list[ClinicRead])
def list_clinics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Clinic]:
    return db.query(Clinic).filter(Clinic.deleted_at.is_(None)).order_by(Clinic.name).all()


@router.get("/{clinic_id}", response_model=ClinicRead)
def get_clinic(
    clinic_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Clinic:
    clinic = db.get(Clinic, clinic_id)
    if clinic is None or clinic.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")
    return clinic