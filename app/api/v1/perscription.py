from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.policies import PRESCRIBING
from app.core.database import get_db
from app.models.mixins import new_uuid
from app.models.perscription import Prescription
from app.models.user import User
from app.schemas.perscription import PrescriptionCreate, PrescriptionRead
from app.services.references import MissingReferenceError, validate_references

router = APIRouter(
    prefix="/prescriptions",
    tags=["prescriptions"],
    dependencies=[Depends(require_roles(*PRESCRIBING))],
)


@router.post("", response_model=PrescriptionRead, status_code=status.HTTP_201_CREATED)
def create_prescription(
    payload: PrescriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Prescription:
    prescription_id = payload.id or new_uuid()
    if db.get(Prescription, prescription_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A prescription with this id already exists.")

    try:
        validate_references(db, Prescription, payload.model_dump(exclude={"id"}))
    except MissingReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    prescription = Prescription(id=prescription_id, **payload.model_dump(exclude={"id"}))
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


@router.get("", response_model=list[PrescriptionRead])
def list_prescriptions(
    consultation_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Prescription]:
    query = db.query(Prescription)
    if consultation_id:
        query = query.filter(Prescription.consultation_id == consultation_id)
    return query.order_by(Prescription.updated_at.desc()).all()


@router.get("/{prescription_id}", response_model=PrescriptionRead)
def get_prescription(
    prescription_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Prescription:
    prescription = db.get(Prescription, prescription_id)
    if prescription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
    return prescription