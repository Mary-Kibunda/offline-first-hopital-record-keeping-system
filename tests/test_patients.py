from fastapi.testclient import TestClient

from app.models.patient import Patient


def test_registry_officer_can_create_and_list_patients(
    auth_client: TestClient, sample_clinic
) -> None:
    response = auth_client.post(
        "/api/v1/patients",
        json={
            "first_name": "Chanda",
            "last_name": "Moyo",
            "date_of_birth": "1988-05-14",
            "gender": "female",
            "registered_clinic_id": sample_clinic.id,
        },
    )
    assert response.status_code == 201, response.text
    patient_id = response.json()["id"]
    assert auth_client.get("/api/v1/patients").json()[0]["id"] == patient_id


def test_patient_rejects_unknown_clinic(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/patients",
        json={
            "first_name": "Chanda",
            "last_name": "Moyo",
            "date_of_birth": "1988-05-14",
            "gender": "female",
            "registered_clinic_id": "missing-clinic-id",
        },
    )
    assert response.status_code == 404


def test_clinician_can_read_patient_records(with_role, client: TestClient, sample_patient: Patient) -> None:
    from app.models.user import UserRole

    with_role(UserRole.clinician)
    response = client.get(f"/api/v1/patients/{sample_patient.id}")
    assert response.status_code == 200


def test_registry_officer_cannot_create_consultation(auth_client: TestClient, sample_patient: Patient) -> None:
    response = auth_client.post(
        "/api/v1/consultations",
        json={
            "patient_id": sample_patient.id,
            "staff_id": "missing-user-id",
            "diagnosis": "Not authorized",
        },
    )
    assert response.status_code == 403


def test_clinician_consultation_checks_related_ids(
    client: TestClient, with_role, sample_patient: Patient
) -> None:
    from app.models.user import UserRole

    clinician = with_role(UserRole.clinician)
    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": sample_patient.id,
            "staff_id": clinician.id,
            "appointment_id": "missing-appointment-id",
            "diagnosis": "Missing references",
        },
    )
    assert response.status_code == 404
    assert "appointment_id" in response.json()["detail"]

    response = client.post(
        "/api/v1/consultations",
        json={
            "patient_id": sample_patient.id,
            "staff_id": "missing-user-id",
            "diagnosis": "Missing staff",
        },
    )
    assert response.status_code == 404
    assert "staff_id" in response.json()["detail"]


def test_appointment_checks_related_patient_and_staff(
    auth_client: TestClient,
) -> None:
    response = auth_client.post(
        "/api/v1/appointments",
        json={
            "patient_id": "missing-patient-id",
            "staff_id": "missing-staff-id",
            "scheduled_at": "2026-10-10T12:00:00Z",
        },
    )
    assert response.status_code == 404
    assert "patient_id" in response.json()["detail"]


def test_drug_stock_checks_related_clinic(client: TestClient, with_role) -> None:
    from app.models.user import UserRole

    with_role(UserRole.pharmacist)
    response = client.post(
        "/api/v1/drug-stock",
        json={
            "clinic_id": "missing-clinic-id",
            "drug_name": "Paracetamol",
            "quantity_available": 10,
            "reorder_threshold": 3,
        },
    )
    assert response.status_code == 404
    assert "clinic_id" in response.json()["detail"]


def test_prescription_checks_related_records(
    client: TestClient, with_role
) -> None:
    from app.models.user import UserRole

    with_role(UserRole.clinician)
    response = client.post(
        "/api/v1/prescriptions",
        json={
            "consultation_id": "missing-consultation-id",
            "drug_id": "missing-drug-id",
            "dosage": "1 tablet",
            "quantity": 1,
        },
    )
    assert response.status_code == 404
    assert "consultation_id" in response.json()["detail"]
