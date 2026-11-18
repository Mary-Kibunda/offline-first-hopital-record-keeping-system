from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.clinic_access import clinic_filter, get_accessible_patient
from app.api.deps import get_current_user, require_roles
from app.api.policies import CLINICAL_AND_REGISTRY
from app.core.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.mixins import new_uuid
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.services.references import MissingReferenceError, validate_references

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
    dependencies=[Depends(require_roles(*CLINICAL_AND_REGISTRY))],
)

_SLOT_CONFLICT_DETAIL = "This staff member already has an appointment at that date and time."


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_appointment_slot(
    db: Session,
    staff_id: str,
    scheduled_at: datetime,
    exclude_appointment_id: str | None = None,
) -> datetime:
    scheduled_at = _utc_datetime(scheduled_at)
    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An appointment must be scheduled for a future date and time.",
        )

    query = db.query(Appointment.id).filter(
        Appointment.staff_id == staff_id,
        Appointment.scheduled_at == scheduled_at,
        Appointment.status.in_(
            [AppointmentStatus.scheduled, AppointmentStatus.rescheduled]
        ),
        Appointment.deleted_at.is_(None),
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)
    if query.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_SLOT_CONFLICT_DETAIL)

    return scheduled_at


def _get_accessible_appointment(
    db: Session,
    appointment_id: str,
    current_user: User,
) -> Appointment:
    query = (
        db.query(Appointment)
        .join(Patient, Appointment.patient_id == Patient.id)
        .options(joinedload(Appointment.patient))
        .filter(Appointment.id == appointment_id, Appointment.deleted_at.is_(None))
    )
    query = clinic_filter(query, Patient.registered_clinic_id, current_user)
    appointment = query.first()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return appointment


def _commit_appointment(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        original_error = exc.orig
        constraint_name = getattr(getattr(original_error, "diag", None), "constraint_name", None)
        sqlite_slot_conflict = (
            str(original_error) == "UNIQUE constraint failed: appointments.staff_id, appointments.scheduled_at"
        )
        if constraint_name == "uq_appointments_staff_scheduled_at_active" or sqlite_slot_conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_SLOT_CONFLICT_DETAIL)
        raise


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

    get_accessible_patient(db, payload.patient_id, current_user)
    staff = db.get(User, payload.staff_id)
    if (
        staff is None
        or (
            current_user.role != UserRole.administrator
            and staff.clinic_id != current_user.clinic_id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )

    appointment_data = payload.model_dump(exclude={"id"})
    if appointment_data["status"] in (
        AppointmentStatus.scheduled,
        AppointmentStatus.rescheduled,
    ):
        appointment_data["scheduled_at"] = _validate_appointment_slot(
            db,
            appointment_data["staff_id"],
            appointment_data["scheduled_at"],
        )

    appointment = Appointment(id=appointment_id, **appointment_data)
    db.add(appointment)
    _commit_appointment(db)
    db.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    patient_id: str | None = Query(default=None),
    staff_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Appointment]:
    query = db.query(Appointment).join(
        Patient, Appointment.patient_id == Patient.id
    ).filter(Appointment.deleted_at.is_(None))
    query = clinic_filter(query, Patient.registered_clinic_id, current_user)
    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if staff_id:
        query = query.filter(Appointment.staff_id == staff_id)
    return query.order_by(Appointment.scheduled_at.desc()).all()


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Appointment:
    return _get_accessible_appointment(db, appointment_id, current_user)


@router.patch("/{appointment_id}", response_model=AppointmentRead)
def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    appointment = _get_accessible_appointment(db, appointment_id, current_user)

    updates = payload.model_dump(exclude_unset=True)
    resulting_status = updates.get("status", appointment.status)
    if resulting_status in (
        AppointmentStatus.scheduled,
        AppointmentStatus.rescheduled,
    ) and ("scheduled_at" in updates or "status" in updates):
        scheduled_at = _validate_appointment_slot(
            db,
            appointment.staff_id,
            updates.get("scheduled_at", appointment.scheduled_at),
            exclude_appointment_id=appointment.id,
        )
        if "scheduled_at" in updates:
            updates["scheduled_at"] = scheduled_at

    for key, value in updates.items():
        setattr(appointment, key, value)
    appointment.version += 1

    _commit_appointment(db)
    db.refresh(appointment)
    return appointment