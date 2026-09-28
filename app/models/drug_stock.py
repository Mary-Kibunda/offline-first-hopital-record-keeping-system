# create drug stock model
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin


class DrugStock(Base, SyncMixin):
    __tablename__ = "drug_stock"

    clinic_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinics.id"), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="drug_stock")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="drug")

    @property
    def needs_reorder(self) -> bool:
        return self.quantity_available <= self.reorder_threshold