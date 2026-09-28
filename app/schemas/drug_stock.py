from datetime import date

from pydantic import BaseModel, Field

from app.schemas.base import SyncMetadataOut


class DrugStockBase(BaseModel):
    clinic_id: str
    drug_name: str = Field(min_length=1, max_length=200)
    quantity_available: int = Field(ge=0, default=0)
    reorder_threshold: int = Field(ge=0, default=10)
    expiry_date: date | None = None


class DrugStockCreate(DrugStockBase):
    id: str | None = None


class DrugStockUpdate(BaseModel):
    quantity_available: int | None = Field(default=None, ge=0)
    reorder_threshold: int | None = Field(default=None, ge=0)
    expiry_date: date | None = None


class DrugStockRead(DrugStockBase, SyncMetadataOut):
    pass