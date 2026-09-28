"""
Shared sync-metadata columns, mixed into every entity that participates in
offline synchronisation (everything except SyncLog itself, which *is* the
log of syncing rather than a synced entity).
"""
import enum
import uuid
from datetime import datetime, timezone
 
from sqlalchemy import DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
 
 
def new_uuid() -> str:
    """Generate a new client-style UUID (as a string) for a primary key."""
    return str(uuid.uuid4())
 
 
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
 
 
class SyncStatus(str, enum.Enum):
    synced = "synced"
    pending = "pending"
    conflict = "conflict"
 
 
def _portable_enum(python_enum: type[enum.Enum]) -> SAEnum:
    """
    Build a SQLAlchemy Enum column type that stores plain VARCHAR values
    with a CHECK constraint (native_enum=False) instead of a PostgreSQL
    native ENUM type. This keeps the column trivially portable to the
    SQLite mirror used on the offline client, and means adding a new enum
    value later is a normal migration rather than an ALTER TYPE.
    """
    return SAEnum(
        python_enum,
        values_callable=lambda obj: [e.value for e in obj],
        native_enum=False,
        validate_strings=True,
    )
 
 
class SyncMixin:
    """
    Columns shared by every syncable entity.
 
    `id` is generated client-side (a UUID string), not a database
    auto-increment value — this is what lets a record created offline carry
    a permanent, collision-resistant identifier before the device has ever
    reached the central server (SRS FR5). It's stored as a plain String
    rather than PostgreSQL's native UUID type so the exact same value/format
    is usable in the SQLite mirror on the client.
    """
 
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    origin_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        _portable_enum(SyncStatus), nullable=False, default=SyncStatus.synced
    )