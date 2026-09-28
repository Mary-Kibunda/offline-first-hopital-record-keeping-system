# create consultation model

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin, utcnow


class Consultation(Base, SyncMixin):
    __tablename__ = "consultations"

    # Nullable: a consultation does not require a prior scheduled appointment
    # (walk-ins are common at first-level hospitals).
    appointment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("appointments.id"), nullable=True
    )
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patient.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    visit_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    appointment: Mapped["Appointment | None"] = relationship(back_populates="consultation")
    patient: Mapped["Patient"] = relationship(back_populates="consultations")
    staff: Mapped["User"] = relationship(back_populates="consultations")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="consultation")