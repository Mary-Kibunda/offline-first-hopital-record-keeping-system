# create appointment model
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .consultation import Consultation
    from .patient import Patient
    from .user import User
import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    missed = "missed"
    cancelled = "cancelled"


class Appointment(Base, SyncMixin):
    __tablename__ = "appointments"

    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patient.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        nullable=False,
        default=AppointmentStatus.scheduled,
    )
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    staff: Mapped["User"] = relationship(back_populates="appointments")
    consultation: Mapped["Consultation | None"] = relationship(back_populates="appointment", uselist=False)