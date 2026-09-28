#create patient schema

from datetime import date

from pydantic import BaseModel, Field

from app.models.patient import Gender
from app.schemas.base import SyncMetadataOut


class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    gender: Gender
    national_id: str | None = Field(default=None, max_length=50)
    village: str | None = Field(default=None, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    next_of_kin: str | None = Field(default=None, max_length=200)
    registered_clinic_id: str


class PatientCreate(PatientBase):
    # Optional client-generated id — set by an offline client before it has
    # ever reached the server (SRS FR5); the server generates one itself
    # when a request doesn't supply it (e.g. a directly-online creation).
    id: str | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    national_id: str | None = Field(default=None, max_length=50)
    village: str | None = Field(default=None, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    next_of_kin: str | None = Field(default=None, max_length=200)


class PatientRead(PatientBase, SyncMetadataOut):
    pass