#create perscription model
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin


class Prescription(Base, SyncMixin):
    __tablename__ = "prescriptions"

    consultation_id: Mapped[str] = mapped_column(String(36), ForeignKey("consultations.id"), nullable=False)
    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drug_stock.id"), nullable=False)
    dosage: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    picked_up: Mapped[bool] = mapped_column(default=False, nullable=False)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    consultation: Mapped["Consultation"] = relationship(back_populates="prescriptions")
    drug: Mapped["DrugStock"] = relationship(back_populates="prescriptions")
    