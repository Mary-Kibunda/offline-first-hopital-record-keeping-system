# create a perscription model

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import SyncMetadataOut
from app.schemas.drug_stock import DrugStockRead


class PrescriptionBase(BaseModel):
    consultation_id: str
    drug_id: str
    dosage: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0)
    picked_up: bool = False
    picked_up_at: datetime | None = None
    picked_up_by_user_id: str | None = None


class PrescriptionCreate(PrescriptionBase):
    id: str | None = None


class PrescriptionRead(PrescriptionBase, SyncMetadataOut):
    pass


class PrescriptionQueueRead(PrescriptionRead):
    clinic_id: str
    patient_id: str
    patient_first_name: str
    patient_last_name: str
    drug_name: str
    drug_quantity_available: int


class PrescriptionDispenseResult(BaseModel):
    prescription: PrescriptionRead
    drug_stock: DrugStockRead
    