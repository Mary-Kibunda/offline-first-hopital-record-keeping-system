# create appointment model
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .consultation import Consultation
    from .patient import Patient
    from .user import User
import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SyncMixin


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    rescheduled = "rescheduled"
    completed = "completed"
    missed = "missed"
    cancelled = "cancelled"


class Appointment(Base, SyncMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_appointments_staff_scheduled_at_active",
            "staff_id",
            "scheduled_at",
            unique=True,
            postgresql_where=text(
                "status IN ('scheduled', 'rescheduled') AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "status IN ('scheduled', 'rescheduled') AND deleted_at IS NULL"
            ),
        ),
    )

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