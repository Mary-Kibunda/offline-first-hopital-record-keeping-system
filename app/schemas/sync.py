"""
Schemas for the offline-sync protocol (SRS FR6-FR9).

The push/pull endpoints are intentionally generic across entity types
(rather than one endpoint per entity) because a single facility device
queues changes across several tables between connections, and the sync
engine needs to push/pull all of them as one batch, not one request per
table.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SyncableEntityType = Literal[
    "patient", "appointment", "consultation", "prescription", "drug_stock"
]


class SyncPushItem(BaseModel):
    """
    One locally-created-or-edited record queued for push. `data` carries the
    entity's own fields (as the matching *Create schema would expect) plus
    its sync metadata (id, version, origin_device_id) — the offline client
    always sets these itself before queuing the record.
    """

    entity_type: SyncableEntityType
    data: dict[str, Any]


class SyncPushRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    items: list[SyncPushItem]


class SyncPushResult(BaseModel):
    entity_type: SyncableEntityType
    entity_id: str
    status: Literal["created", "updated", "conflict", "rejected"]
    server_version: int | None = None
    detail: str | None = None


class SyncPushResponse(BaseModel):
    results: list[SyncPushResult]


class SyncPullResponse(BaseModel):
    server_time: datetime
    patients: list[dict[str, Any]] = Field(default_factory=list)
    appointments: list[dict[str, Any]] = Field(default_factory=list)
    consultations: list[dict[str, Any]] = Field(default_factory=list)
    prescriptions: list[dict[str, Any]] = Field(default_factory=list)
    drug_stock: list[dict[str, Any]] = Field(default_factory=list)


class ConflictResolutionRequest(BaseModel):
    keep_local: bool
    local_data: dict[str, Any] | None = None


class SyncLogRead(BaseModel):
    id: str
    user_id: str | None = None
    user_name: str | None = None
    device_id: str
    entity_type: str
    entity_id: str
    operation: str
    conflict_detected: bool
    conflict_resolved: bool
    resolution_strategy: str | None
    synced_at: datetime

    model_config = {"from_attributes": True}
