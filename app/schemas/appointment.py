from datetime import datetime

from pydantic import BaseModel, Field

from app.models.appointment import AppointmentStatus
from app.schemas.base import SyncMetadataOut


class AppointmentBase(BaseModel):
    patient_id: str
    staff_id: str
    scheduled_at: datetime
    status: AppointmentStatus = AppointmentStatus.scheduled
    reason: str | None = Field(default=None, max_length=300)


class AppointmentCreate(AppointmentBase):
    id: str | None = None


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = None
    status: AppointmentStatus | None = None
    reason: str | None = Field(default=None, max_length=300)


class AppointmentRead(AppointmentBase, SyncMetadataOut):
    pass