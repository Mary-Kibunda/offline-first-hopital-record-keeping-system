from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.clinic_access import clinic_filter
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.consultation import Consultation
from app.models.drug_stock import DrugStock
from app.models.mixins import SyncStatus, new_uuid, utcnow
from app.models.patient import Patient
from app.models.perscription import Prescription
from app.models.user import User, UserRole
from app.schemas.drug_stock import DrugStockRead
from app.schemas.perscription import (
    PrescriptionCreate,
    PrescriptionDispenseResult,
    PrescriptionQueueRead,
    PrescriptionRead,
)

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


def _accessible_prescription_query(db: Session, current_user: User):
    query = (
        db.query(Prescription)
        .join(Consultation, Prescription.consultation_id == Consultation.id)
        .join(Patient, Consultation.patient_id == Patient.id)
        .join(DrugStock, Prescription.drug_id == DrugStock.id)
        .options(
            joinedload(Prescription.consultation).joinedload(Consultation.patient),
            joinedload(Prescription.drug),
        )
        .filter(Prescription.deleted_at.is_(None))
        .filter(DrugStock.clinic_id == Patient.registered_clinic_id)
    )
    return clinic_filter(query, Patient.registered_clinic_id, current_user)


@router.post("", response_model=PrescriptionRead, status_code=status.HTTP_201_CREATED)
def create_prescription(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Prescription:
    if current_user.role == UserRole.pharmacist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pharmacists cannot create prescriptions.",
        )

    consultation = (
        db.query(Consultation)
        .join(Patient, Consultation.patient_id == Patient.id)
        .filter(Consultation.id == payload.consultation_id)
    )
    consultation = clinic_filter(
        consultation, Patient.registered_clinic_id, current_user
    ).first()
    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found",
        )

    drug = db.get(DrugStock, payload.drug_id)
    if drug is None or drug.clinic_id != consultation.patient.registered_clinic_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drug stock entry not found at this clinic",
        )

    prescription_id = payload.id or new_uuid()
    if db.get(Prescription, prescription_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A prescription with this id already exists.",
        )

    prescription = Prescription(
        id=prescription_id,
        **payload.model_dump(exclude={"id", "picked_up", "picked_up_at", "picked_up_by_user_id"}),
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


@router.get("", response_model=list[PrescriptionQueueRead])
def list_prescriptions(
    current_user: User = Depends(
        require_roles(UserRole.administrator, UserRole.pharmacist)
    ),
    db: Session = Depends(get_db),
) -> list[PrescriptionQueueRead]:
    rows = _accessible_prescription_query(db, current_user).order_by(
        Prescription.updated_at.desc()
    ).all()
    return [
        PrescriptionQueueRead(
            **PrescriptionRead.model_validate(row).model_dump(),
            clinic_id=row.consultation.patient.registered_clinic_id,
            patient_id=row.consultation.patient_id,
            patient_first_name=row.consultation.patient.first_name,
            patient_last_name=row.consultation.patient.last_name,
            drug_name=row.drug.drug_name,
            drug_quantity_available=row.drug.quantity_available,
        )
        for row in rows
    ]


@router.get("/{prescription_id}", response_model=PrescriptionRead)
def get_prescription(
    prescription_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Prescription:
    prescription = _accessible_prescription_query(db, current_user).filter(
        Prescription.id == prescription_id
    ).first()
    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found",
        )
    return prescription


@router.post(
    "/{prescription_id}/dispense",
    response_model=PrescriptionDispenseResult,
)
def dispense_prescription(
    prescription_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.pharmacist)),
) -> PrescriptionDispenseResult:
    prescription = _accessible_prescription_query(db, current_user).filter(
        Prescription.id == prescription_id
    ).with_for_update().first()
    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found",
        )

    drug = (
        db.query(DrugStock)
        .filter(DrugStock.id == prescription.drug_id)
        .with_for_update()
        .first()
    )
    if drug is None or drug.clinic_id != prescription.consultation.patient.registered_clinic_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drug stock entry not found at this clinic",
        )

    if not prescription.picked_up:
        if drug.quantity_available < prescription.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="There is not enough stock to dispense this prescription.",
            )
        now = utcnow()
        drug.quantity_available -= prescription.quantity
        drug.version += 1
        drug.updated_at = now
        drug.sync_status = SyncStatus.synced
        prescription.picked_up = True
        prescription.picked_up_at = now
        prescription.picked_up_by_user_id = current_user.id
        prescription.version += 1
        prescription.updated_at = now
        prescription.sync_status = SyncStatus.synced
        db.commit()
        db.refresh(drug)
        db.refresh(prescription)

    return PrescriptionDispenseResult(
        prescription=PrescriptionRead.model_validate(prescription),
        drug_stock=DrugStockRead.model_validate(drug),
    )
