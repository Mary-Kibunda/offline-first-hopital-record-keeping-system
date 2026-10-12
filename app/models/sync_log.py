#create a sync log model

from datetime import datetime
import enum
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from app.core.database import Base
from sqlalchemy import Enum as SAEnum
from app.core.database import Base
from app.models.mixins import new_uuid, utcnow
from sqlalchemy.orm import Mapped, mapped_column

class SyncOperation(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"

class SyncLog(Base):
  __tablename__ = "sync_log"

  id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
  user_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("users.id"), nullable=True, index=True
  )
  device_id: Mapped[str] = mapped_column(String(64), nullable=False)
  entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
  entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
  operation: Mapped[SyncOperation] = mapped_column(
    SAEnum(SyncOperation, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
    nullable=False,
  )
  conflict_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  conflict_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  resolution_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
  synced_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, default=utcnow
  )