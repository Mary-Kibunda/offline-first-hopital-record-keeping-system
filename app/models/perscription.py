#create perscription model
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin


class Prescription(Base, SyncMixin):
    __tablename__ = "prescriptions"

    consultation_id: Mapped[str] = mapped_column(String(36), ForeignKey("consultations.id"), nullable=False)
    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drug_stock.id"), nullable=False)
    dosage: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    consultation: Mapped["Consultation"] = relationship(back_populates="prescriptions")
    drug: Mapped["DrugStock"] = relationship(back_populates="prescriptions")
    