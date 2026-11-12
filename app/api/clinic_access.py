from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.user import User, UserRole


def clinic_filter(query, clinic_column, current_user: User):
    """Limit a query to the caller's clinic while allowing administrators global scope."""
    if current_user.role != UserRole.administrator:
        query = query.filter(clinic_column == current_user.clinic_id)
    return query


def get_accessible_patient(db: Session, patient_id: str, current_user: User) -> Patient:
    query = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    query = clinic_filter(query, Patient.registered_clinic_id, current_user)
    patient = query.first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient
