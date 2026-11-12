from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.clinic_access import clinic_filter, get_accessible_patient
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.mixins import new_uuid
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Patient:
    if (
        current_user.role != UserRole.administrator
        and payload.registered_clinic_id != current_user.clinic_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register patients at your assigned clinic.",
        )

    patient_id = payload.id or new_uuid()
    if db.get(Patient, patient_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A patient with this id already exists.")

    patient = Patient(id=patient_id, origin_device_id=None, **payload.model_dump(exclude={"id"}))
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientRead])
def search_patients(
    q: str | None = Query(default=None, description="Search by name, national ID, or village"),
    clinic_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Patient]:
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))
    if current_user.role == UserRole.administrator:
        if clinic_id:
            query = query.filter(Patient.registered_clinic_id == clinic_id)
    else:
        query = clinic_filter(query, Patient.registered_clinic_id, current_user)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.national_id.ilike(like),
                Patient.village.ilike(like),
            )
        )

    return query.order_by(Patient.updated_at.desc()).limit(limit).all()


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(
    patient_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Patient:
    return get_accessible_patient(db, patient_id, current_user)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Patient:
    patient = get_accessible_patient(db, patient_id, current_user)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    patient.version += 1

    db.commit()
    db.refresh(patient)
    return patient