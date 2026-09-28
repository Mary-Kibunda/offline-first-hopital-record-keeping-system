from pydantic import BaseModel, Field

from app.schemas.base import SyncMetadataOut


class ClinicBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)


class ClinicCreate(ClinicBase):
    id: str | None = None


class ClinicRead(ClinicBase, SyncMetadataOut):
    pass