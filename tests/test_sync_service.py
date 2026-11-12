from datetime import date

from app.models.patient import Patient
from app.schemas.sync import SyncPushItem
from app.services.sync_service import pull_updates, push_item


def test_sync_push_rejects_unknown_foreign_key(db_session) -> None:
    item = SyncPushItem(
        entity_type="patient",
        data={
            "id": "patient-with-missing-clinic",
            "first_name": "No",
            "last_name": "Clinic",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "registered_clinic_id": "missing-clinic-id",
        },
    )
    result = push_item(db_session, "device-1", item)
    assert result.status == "rejected"
    assert db_session.get(Patient, "patient-with-missing-clinic") is None


def test_sync_push_creates_entity_and_pull_can_filter_types(db_session, sample_clinic) -> None:
    item = SyncPushItem(
        entity_type="patient",
        data={
            "id": "patient-for-sync",
            "first_name": "Sync",
            "last_name": "Patient",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "registered_clinic_id": sample_clinic.id,
        },
    )
    result = push_item(db_session, "device-1", item)
    assert result.status == "created"
    pulled = pull_updates(db_session, None, {"patient"})
    assert set(pulled) == {"patient"}
    assert pulled["patient"][0]["id"] == "patient-for-sync"


def test_sync_pull_filters_entities(db_session, sample_clinic) -> None:
    patient = Patient(
        registered_clinic_id=sample_clinic.id,
        first_name="Visible",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        gender="male",
    )
    db_session.add(patient)
    db_session.flush()

    assert pull_updates(db_session, None, {"drug_stock"}) == {"drug_stock": []}
    assert db_session.query(Patient).count() == 1
