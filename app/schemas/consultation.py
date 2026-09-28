#create a consultation schema

from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import SyncMetadataOut


class ConsultationBase(BaseModel):
    patient_id: str
    staff_id: str
    appointment_id: str | None = None
    visit_date: datetime | None = None
    symptoms: str | None = None
    diagnosis: str
    notes: str | None = None


class ConsultationCreate(ConsultationBase):
    id: str | None = None


class ConsultationUpdate(BaseModel):
    symptoms: str | None = None
    diagnosis: str | None = None
    notes: str | None = None


class ConsultationRead(ConsultationBase, SyncMetadataOut):
    visit_date: datetime