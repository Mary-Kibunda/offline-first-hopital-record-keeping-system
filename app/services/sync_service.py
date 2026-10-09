"""
The sync engine's server-side counterpart.

Conflict-detection policy (documented here because it's the single most
important design decision in the whole project):

  1. Record doesn't exist on the server yet          -> insert it ("created")
  2. Record exists, incoming.version > server.version -> apply the update
     ("updated"). We treat a strictly higher incoming version as a clean,
     sequential edit built on top of what the server already has.
  3. Record exists, incoming.version <= server.version:
       a. If the incoming field values are identical to what's already
          stored, this is a harmless retry/re-push of something already
          applied — no-op, reported as "updated" (idempotent).
       b. Otherwise, two devices independently edited the same base version
          before either had synced — a genuine conflict. The server record
          is left untouched but flagged `sync_status = conflict`, logged,
          and reported back as "conflict" so the offline client can surface
          it for manual resolution (see resolve_conflict()), matching the
          Sync Status screen's "keep this device's version / keep server
          version" choice.
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.drug_stock import DrugStock
from app.models.mixins import SyncStatus, new_uuid
from app.models.patient import Patient
from app.models.perscription import Prescription
from app.models.sync_log import SyncLog, SyncOperation
from app.schemas.appointment import AppointmentCreate
from app.schemas.consultation import ConsultationCreate
from app.schemas.drug_stock import DrugStockCreate
from app.schemas.patient import PatientCreate
from app.schemas.perscription import PrescriptionCreate
from app.schemas.sync import SyncPushItem, SyncPushResult

_REGISTRY: dict[str, tuple[type, type[BaseModel]]] = {
    "patient": (Patient, PatientCreate),
    "appointment": (Appointment, AppointmentCreate),
    "consultation": (Consultation, ConsultationCreate),
    "prescription": (Prescription, PrescriptionCreate),
    "drug_stock": (DrugStock, DrugStockCreate),
}

# Columns that belong to sync metadata, not to the entity's own Create
# schema — handled separately rather than passed through model_dump().
_SYNC_META_KEYS = {"id", "version", "origin_device_id", "sync_status", "deleted_at", "updated_at"}


class UnknownEntityTypeError(ValueError):
    pass


class InvalidPayloadError(ValueError):
    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__(str(errors))


def _entity_fields_differ(existing: Any, incoming_fields: dict[str, Any]) -> bool:
    """True if any incoming field value differs from what's already stored."""
    for key, value in incoming_fields.items():
        if getattr(existing, key, object()) != value:
            return True
    return False


def push_item(db: Session, device_id: str, user_id: str, item: SyncPushItem) -> SyncPushResult:
    """Apply one queued record to the database, per the policy above."""
    registry_entry = _REGISTRY.get(item.entity_type)
    if registry_entry is None:
        raise UnknownEntityTypeError(item.entity_type)
    model_cls, schema_cls = registry_entry

    raw = dict(item.data)
    entity_id = raw.get("id") or new_uuid()
    incoming_version = int(raw.get("version", 1))
    origin_device_id = raw.get("origin_device_id", device_id)

    entity_fields = {k: v for k, v in raw.items() if k not in _SYNC_META_KEYS}
    try:
        validated = schema_cls.model_validate({**entity_fields, "id": entity_id})
    except ValidationError as exc:
        return SyncPushResult(
            entity_type=item.entity_type,
            entity_id=entity_id,
            status="rejected",
            detail=f"Validation failed: {exc.errors()}",
        )
    clean_fields = validated.model_dump(exclude={"id"})

    existing = db.get(model_cls, entity_id)

    if existing is None:
        record = model_cls(
            id=entity_id,
            version=incoming_version,
            origin_device_id=origin_device_id,
            sync_status=SyncStatus.synced,
            **clean_fields,
        )
        db.add(record)
        db.flush()
        _log(db, device_id, user_id, item.entity_type, entity_id, SyncOperation.create, conflict=False)
        return SyncPushResult(
            entity_type=item.entity_type, entity_id=entity_id, status="created", server_version=incoming_version
        )

    if incoming_version > existing.version:
        for key, value in clean_fields.items():
            setattr(existing, key, value)
        existing.version = incoming_version
        existing.origin_device_id = origin_device_id
        existing.sync_status = SyncStatus.synced
        db.flush()
        _log(db, device_id, user_id, item.entity_type, entity_id, SyncOperation.update, conflict=False)
        return SyncPushResult(
            entity_type=item.entity_type, entity_id=entity_id, status="updated", server_version=incoming_version
        )

    # incoming_version <= existing.version
    if not _entity_fields_differ(existing, clean_fields):
        # Idempotent retry of something already applied — not a conflict.
        return SyncPushResult(
            entity_type=item.entity_type,
            entity_id=entity_id,
            status="updated",
            server_version=existing.version,
            detail="No changes — already up to date.",
        )

    existing.sync_status = SyncStatus.conflict
    db.flush()
    _log(db, device_id, user_id, item.entity_type, entity_id, SyncOperation.update, conflict=True)
    return SyncPushResult(
        entity_type=item.entity_type,
        entity_id=entity_id,
        status="conflict",
        server_version=existing.version,
        detail="This record was edited on another device before this device's edit could sync.",
    )


def _log(
    db: Session,
    device_id: str,
    user_id: str,
    entity_type: str,
    entity_id: str,
    operation: SyncOperation,
    *,
    conflict: bool,
) -> None:
    db.add(
        SyncLog(
            user_id=user_id,
            device_id=device_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            conflict_detected=conflict,
            conflict_resolved=not conflict,
        )
    )


def pull_updates(db: Session, since: datetime | None) -> dict[str, list[dict[str, Any]]]:
    """
    Return every record across all syncable entities updated after `since`
    (or everything, if `since` is None — a device's very first sync).
    """
    result: dict[str, list[dict[str, Any]]] = {}
    for entity_type, (model_cls, _schema_cls) in _REGISTRY.items():
        query = db.query(model_cls)
        if since is not None:
            query = query.filter(model_cls.updated_at > since)
        rows = query.all()
        result[entity_type] = [_row_to_dict(row) for row in rows]
    return result


def _row_to_dict(row: Any) -> dict[str, Any]:
    columns = row.__table__.columns.keys()
    out: dict[str, Any] = {}
    for col in columns:
        value = getattr(row, col)
        out[col] = value
    return out


def resolve_conflict(
    db: Session, entity_type: str, entity_id: str, *, keep_local: bool, local_data: dict[str, Any] | None
) -> SyncPushResult:
    """
    Apply a staff member's manual decision on a flagged conflict (the
    Sync Status screen's "keep this device's version" / "keep server
    version" buttons).
    """
    registry_entry = _REGISTRY.get(entity_type)
    if registry_entry is None:
        raise UnknownEntityTypeError(entity_type)
    model_cls, schema_cls = registry_entry

    existing = db.get(model_cls, entity_id)
    if existing is None:
        raise ValueError(f"No {entity_type} with id {entity_id}")

    if keep_local:
        if not local_data:
            raise ValueError("local_data is required when keep_local is true")
        entity_fields = {k: v for k, v in local_data.items() if k not in _SYNC_META_KEYS}
        validated = schema_cls.model_validate({**entity_fields, "id": entity_id})
        for key, value in validated.model_dump(exclude={"id"}).items():
            setattr(existing, key, value)
        existing.version += 1

    existing.sync_status = SyncStatus.synced
    db.flush()

    log_entry = (
        db.query(SyncLog)
        .filter(SyncLog.entity_type == entity_type, SyncLog.entity_id == entity_id, SyncLog.conflict_detected.is_(True))
        .order_by(SyncLog.synced_at.desc())
        .first()
    )
    if log_entry is not None:
        log_entry.conflict_resolved = True
        log_entry.resolution_strategy = "manual-keep-local" if keep_local else "manual-keep-server"

    return SyncPushResult(
        entity_type=entity_type,  # type: ignore[arg-type]
        entity_id=entity_id,
        status="updated",
        server_version=existing.version,
    )