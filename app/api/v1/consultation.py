from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.clinic_access import clinic_filter, get_accessible_patient
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.consultation import Consultation
from app.models.mixins import new_uuid, utcnow
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.consultation import ConsultationCreate, ConsultationRead, ConsultationUpdate

router = APIRouter(prefix="/consultations", tags=["consultations"])


def _get_accessible_consultation(
    db: Session,
    consultation_id: str,
    current_user: User,
) -> Consultation:
    query = (
        db.query(Consultation)
        .join(Patient, Consultation.patient_id == Patient.id)
        .options(joinedload(Consultation.patient))
        .filter(
            Consultation.id == consultation_id,
            Consultation.deleted_at.is_(None),
        )
    )
    query = clinic_filter(query, Patient.registered_clinic_id, current_user)
    consultation = query.first()
    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found",
        )
    return consultation


@router.post("", response_model=ConsultationRead, status_code=status.HTTP_201_CREATED)
def create_consultation(
    payload: ConsultationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Consultation:
    consultation_id = payload.id or new_uuid()
    if db.get(Consultation, consultation_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A consultation with this id already exists.")

    patient = get_accessible_patient(db, payload.patient_id, current_user)
    staff = db.get(User, payload.staff_id)
    if (
        staff is None
        or (
            current_user.role != UserRole.administrator
            and staff.clinic_id != patient.registered_clinic_id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    data = payload.model_dump(exclude={"id"})
    if data.get("visit_date") is None:
        data["visit_date"] = utcnow()

    consultation = Consultation(id=consultation_id, **data)
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return consultation


@router.get("", response_model=list[ConsultationRead])
def list_consultations(
    patient_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Consultation]:
    query = (
        db.query(Consultation)
        .join(Patient, Consultation.patient_id == Patient.id)
        .filter(Consultation.deleted_at.is_(None))
    )
    query = clinic_filter(query, Patient.registered_clinic_id, current_user)
    if patient_id:
        query = query.filter(Consultation.patient_id == patient_id)
    return query.order_by(Consultation.visit_date.desc()).all()


@router.get("/{consultation_id}", response_model=ConsultationRead)
def get_consultation(
    consultation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Consultation:
    return _get_accessible_consultation(db, consultation_id, current_user)


@router.patch("/{consultation_id}", response_model=ConsultationRead)
def update_consultation(
    consultation_id: str,
    payload: ConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Consultation:
    consultation = _get_accessible_consultation(db, consultation_id, current_user)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(consultation, key, value)
    consultation.version += 1

    db.commit()
    db.refresh(consultation)
    return consultation