"""
Shared base classes for request/response schemas.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.mixins import SyncStatus


class SyncMetadataOut(BaseModel):
    """
    The sync-related fields every syncable entity exposes in its Read
    schema, so API consumers (including the offline client reconciling its
    local SQLite copy) can see version/sync state without a separate call.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    origin_device_id: str | None = None
    updated_at: datetime
    deleted_at: datetime | None = None
    sync_status: SyncStatus