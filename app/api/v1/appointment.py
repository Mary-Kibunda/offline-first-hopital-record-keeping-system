from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.policies import CLINICAL_AND_REGISTRY
from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.mixins import new_uuid
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.services.references import MissingReferenceError, validate_references

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
    dependencies=[Depends(require_roles(*CLINICAL_AND_REGISTRY))],
)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Appointment:
    appointment_id = payload.id or new_uuid()
    if db.get(Appointment, appointment_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An appointment with this id already exists.")

    try:
        validate_references(db, Appointment, payload.model_dump(exclude={"id"}))
    except MissingReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    appointment = Appointment(id=appointment_id, **payload.model_dump(exclude={"id"}))
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    patient_id: str | None = Query(default=None),
    staff_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Appointment]:
    query = db.query(Appointment)
    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if staff_id:
        query = query.filter(Appointment.staff_id == staff_id)
    return query.order_by(Appointment.scheduled_at.desc()).all()


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentRead)
def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(appointment, key, value)
    appointment.version += 1

    db.commit()
    db.refresh(appointment)
    return appointment