from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.policies import CLINICAL
from app.core.database import get_db
from app.models.consultation import Consultation
from app.models.mixins import new_uuid, utcnow
from app.models.user import User
from app.schemas.consultation import ConsultationCreate, ConsultationRead, ConsultationUpdate
from app.services.references import MissingReferenceError, validate_references

router = APIRouter(
    prefix="/consultations",
    tags=["consultations"],
    dependencies=[Depends(require_roles(*CLINICAL))],
)


@router.post("", response_model=ConsultationRead, status_code=status.HTTP_201_CREATED)
def create_consultation(
    payload: ConsultationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Consultation:
    consultation_id = payload.id or new_uuid()
    if db.get(Consultation, consultation_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A consultation with this id already exists.")

    data = payload.model_dump(exclude={"id"})
    if data.get("visit_date") is None:
        data["visit_date"] = utcnow()

    try:
        validate_references(db, Consultation, data)
    except MissingReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

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
    query = db.query(Consultation)
    if patient_id:
        query = query.filter(Consultation.patient_id == patient_id)
    return query.order_by(Consultation.visit_date.desc()).all()


@router.get("/{consultation_id}", response_model=ConsultationRead)
def get_consultation(
    consultation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Consultation:
    consultation = db.get(Consultation, consultation_id)
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return consultation


@router.patch("/{consultation_id}", response_model=ConsultationRead)
def update_consultation(
    consultation_id: str,
    payload: ConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Consultation:
    consultation = db.get(Consultation, consultation_id)
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(consultation, key, value)
    consultation.version += 1

    db.commit()
    db.refresh(consultation)
    return consultation