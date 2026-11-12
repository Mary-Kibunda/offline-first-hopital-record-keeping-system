from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.clinic import Clinic
from app.models.consultation import Consultation
from app.models.drug_stock import DrugStock
from app.models.patient import Gender, Patient
from app.models.perscription import Prescription
from app.models.user import User, UserRole


def _patient(db_session, clinic_id: str, name: str) -> Patient:
    patient = Patient(
        registered_clinic_id=clinic_id,
        first_name=name,
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.female,
    )
    db_session.add(patient)
    db_session.flush()
    return patient


def _pharmacist(db_session, clinic_id: str) -> User:
    pharmacist = User(
        name="Clinic Pharmacist",
        username=f"pharmacist-{clinic_id}",
        role=UserRole.pharmacist,
        clinic_id=clinic_id,
        password_hash="test-password-hash",
    )
    db_session.add(pharmacist)
    db_session.flush()
    return pharmacist


def _prescription_fixture(db_session, clinic_id: str, patient_name: str):
    patient = _patient(db_session, clinic_id, patient_name)
    pharmacist = _pharmacist(db_session, clinic_id)
    stock = DrugStock(
        clinic_id=clinic_id,
        drug_name="Paracetamol",
        quantity_available=10,
        reorder_threshold=2,
    )
    db_session.add(stock)
    db_session.flush()
    consultation = Consultation(
        patient_id=patient.id,
        staff_id=pharmacist.id,
        visit_date=datetime.now(timezone.utc),
        diagnosis="Fever",
    )
    db_session.add(consultation)
    db_session.flush()
    prescription = Prescription(
        consultation_id=consultation.id,
        drug_id=stock.id,
        dosage="500 mg",
        quantity=3,
    )
    db_session.add(prescription)
    db_session.flush()
    return pharmacist, patient, stock, prescription


def test_pharmacist_cannot_read_patient_from_another_clinic(
    client: TestClient, db_session, sample_clinic
) -> None:
    other_clinic = Clinic(name="Other Clinic", location="Other")
    db_session.add(other_clinic)
    db_session.flush()
    pharmacist, _, _, _ = _prescription_fixture(
        db_session, sample_clinic.id, "Local"
    )
    other_patient = _patient(db_session, other_clinic.id, "Other")
    app.dependency_overrides[get_current_user] = lambda: pharmacist

    try:
        response = client.get(f"/api/v1/patients/{other_patient.id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404


def test_sync_pull_and_prescription_queue_are_clinic_scoped(
    client: TestClient, db_session, sample_clinic
) -> None:
    other_clinic = Clinic(name="Other Clinic", location="Other")
    db_session.add(other_clinic)
    db_session.flush()
    pharmacist, local_patient, _, _ = _prescription_fixture(
        db_session, sample_clinic.id, "Local"
    )
    _prescription_fixture(db_session, other_clinic.id, "Remote")
    app.dependency_overrides[get_current_user] = lambda: pharmacist

    try:
        pulled = client.get("/api/v1/sync/pull")
        queued = client.get("/api/v1/prescriptions")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert pulled.status_code == 200
    assert {row["id"] for row in pulled.json()["patients"]} == {local_patient.id}
    assert queued.status_code == 200
    assert len(queued.json()) == 1
    assert queued.json()[0]["patient_id"] == local_patient.id


def test_sync_push_can_read_existing_prescription_with_pickup_fields(
    client: TestClient, db_session, sample_clinic
) -> None:
    pharmacist, _, _, prescription = _prescription_fixture(
        db_session, sample_clinic.id, "Sync"
    )
    app.dependency_overrides[get_current_user] = lambda: pharmacist

    try:
        response = client.post(
            "/api/v1/sync/push",
            json={
                "device_id": "sync-device",
                "items": [
                    {
                        "entity_type": "prescription",
                        "data": {
                            "id": prescription.id,
                            "version": prescription.version,
                            "origin_device_id": "sync-device",
                            "consultation_id": prescription.consultation_id,
                            "drug_id": prescription.drug_id,
                            "dosage": prescription.dosage,
                            "quantity": prescription.quantity,
                            "picked_up": prescription.picked_up,
                            "picked_up_at": prescription.picked_up_at,
                            "picked_up_by_user_id": prescription.picked_up_by_user_id,
                        },
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["entity_id"] == prescription.id
    assert result["status"] == "updated"


def test_dispensing_decrements_stock_once_and_is_idempotent(
    client: TestClient, db_session, sample_clinic
) -> None:
    pharmacist, _, stock, prescription = _prescription_fixture(
        db_session, sample_clinic.id, "Pickup"
    )
    app.dependency_overrides[get_current_user] = lambda: pharmacist

    try:
        first_response = client.post(
            f"/api/v1/prescriptions/{prescription.id}/dispense"
        )
        second_response = client.post(
            f"/api/v1/prescriptions/{prescription.id}/dispense"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert first_response.json()["prescription"]["picked_up"] is True
    db_session.refresh(stock)
    assert stock.quantity_available == 7


def test_dispensing_rejects_insufficient_stock_without_mutating(
    client: TestClient, db_session, sample_clinic
) -> None:
    pharmacist, _, stock, prescription = _prescription_fixture(
        db_session, sample_clinic.id, "Insufficient"
    )
    stock.quantity_available = 2
    app.dependency_overrides[get_current_user] = lambda: pharmacist

    try:
        response = client.post(
            f"/api/v1/prescriptions/{prescription.id}/dispense"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 409
    db_session.refresh(stock)
    db_session.refresh(prescription)
    assert stock.quantity_available == 2
    assert prescription.picked_up is False


def test_appointment_can_be_rescheduled(
    client: TestClient, db_session, sample_clinic
) -> None:
    clinician = User(
        name="Clinic Clinician",
        username="reschedule-clinician",
        role=UserRole.clinician,
        clinic_id=sample_clinic.id,
        password_hash="test-password-hash",
    )
    db_session.add(clinician)
    db_session.flush()
    patient = _patient(db_session, sample_clinic.id, "Appointment")
    from app.models.appointment import Appointment

    appointment = Appointment(
        patient_id=patient.id,
        staff_id=clinician.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.add(appointment)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: clinician

    try:
        response = client.patch(
            f"/api/v1/appointments/{appointment.id}",
            json={
                "status": "rescheduled",
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rescheduled"
