from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.appointment import Appointment
from app.models.patient import Gender, Patient
from app.models.user import User, UserRole


@pytest.fixture
def appointment_context(client: TestClient, db_session, sample_clinic) -> Generator[tuple[TestClient, User], None, None]:
    staff = User(
        name="Appointment Clinician",
        username="appointment.clinician",
        role=UserRole.clinician,
        clinic_id=sample_clinic.id,
        password_hash="test-password-hash",
    )
    db_session.add(staff)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: staff
    yield client, staff
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def appointment_patient(db_session, sample_clinic) -> Patient:
    patient = Patient(
        registered_clinic_id=sample_clinic.id,
        first_name="Chanda",
        last_name="Mbewe",
        date_of_birth=datetime(1990, 1, 1).date(),
        gender=Gender.female,
    )
    db_session.add(patient)
    db_session.flush()
    return patient


def _future_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=2)


def _appointment_payload(patient_id: str, staff_id: str, scheduled_at: datetime) -> dict[str, str]:
    return {
        "patient_id": patient_id,
        "staff_id": staff_id,
        "scheduled_at": scheduled_at.isoformat(),
    }


def test_list_appointments_returns_clinic_appointments(
    appointment_context: tuple[TestClient, User],
    db_session,
    appointment_patient: Patient,
) -> None:
    client, staff = appointment_context
    appointment = Appointment(
        patient_id=appointment_patient.id,
        staff_id=staff.id,
        scheduled_at=_future_time(),
    )
    db_session.add(appointment)
    db_session.flush()

    response = client.get("/api/v1/appointments")

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [appointment.id]


def test_create_appointment_rejects_past_datetime(
    appointment_context: tuple[TestClient, User],
    appointment_patient: Patient,
) -> None:
    client, staff = appointment_context
    response = client.post(
        "/api/v1/appointments",
        json=_appointment_payload(
            appointment_patient.id,
            staff.id,
            datetime.now(timezone.utc) - timedelta(days=1),
        ),
    )

    assert response.status_code == 422
    assert "future date and time" in response.json()["detail"]


def test_create_appointment_accepts_available_future_slot(
    appointment_context: tuple[TestClient, User],
    appointment_patient: Patient,
) -> None:
    client, staff = appointment_context
    scheduled_at = _future_time()

    response = client.post(
        "/api/v1/appointments",
        json=_appointment_payload(appointment_patient.id, staff.id, scheduled_at),
    )

    assert response.status_code == 201, response.text
    assert response.json()["patient_id"] == appointment_patient.id


def test_create_appointment_rejects_slot_reserved_for_another_patient(
    appointment_context: tuple[TestClient, User],
    db_session,
    appointment_patient: Patient,
) -> None:
    client, staff = appointment_context
    scheduled_at = _future_time()
    existing_patient = Patient(
        registered_clinic_id=appointment_patient.registered_clinic_id,
        first_name="Tapiwa",
        last_name="Phiri",
        date_of_birth=datetime(1985, 1, 1).date(),
        gender=Gender.male,
    )
    db_session.add(existing_patient)
    db_session.flush()
    db_session.add(
        Appointment(
            patient_id=existing_patient.id,
            staff_id=staff.id,
            scheduled_at=scheduled_at,
        )
    )
    db_session.flush()

    response = client.post(
        "/api/v1/appointments",
        json=_appointment_payload(appointment_patient.id, staff.id, scheduled_at),
    )

    assert response.status_code == 409
    assert "already has an appointment" in response.json()["detail"]


def test_update_appointment_rejects_reserved_slot(
    appointment_context: tuple[TestClient, User],
    db_session,
    appointment_patient: Patient,
) -> None:
    client, staff = appointment_context
    scheduled_at = _future_time()
    existing_patient = Patient(
        registered_clinic_id=appointment_patient.registered_clinic_id,
        first_name="Tapiwa",
        last_name="Phiri",
        date_of_birth=datetime(1985, 1, 1).date(),
        gender=Gender.male,
    )
    first_appointment = Appointment(
        patient_id=appointment_patient.id,
        staff_id=staff.id,
        scheduled_at=scheduled_at,
    )
    db_session.add_all(
        [
            existing_patient,
            first_appointment,
        ]
    )
    db_session.flush()
    db_session.add(
        Appointment(
            patient_id=existing_patient.id,
            staff_id=staff.id,
            scheduled_at=scheduled_at + timedelta(hours=1),
        )
    )
    db_session.flush()

    response = client.patch(
        f"/api/v1/appointments/{first_appointment.id}",
        json={"scheduled_at": (scheduled_at + timedelta(hours=1)).isoformat()},
    )

    assert response.status_code == 409
