# create a perscription model

from pydantic import BaseModel, Field

from app.schemas.base import SyncMetadataOut


class PrescriptionBase(BaseModel):
    consultation_id: str
    drug_id: str
    dosage: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0)


class PrescriptionCreate(PrescriptionBase):
    id: str | None = None


class PrescriptionRead(PrescriptionBase, SyncMetadataOut):
    pass
    