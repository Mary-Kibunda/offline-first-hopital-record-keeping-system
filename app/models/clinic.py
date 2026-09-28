# clinic or hospital model

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
 
from app.core.database import Base
from app.models.mixins import SyncMixin
 
 
class Clinic(Base, SyncMixin):
    __tablename__ = "clinics"
 
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
 
    users: Mapped[list["User"]] = relationship(back_populates="clinic")
    patients: Mapped[list["Patient"]] = relationship(back_populates="registered_clinic")
    drug_stock: Mapped[list["DrugStock"]] = relationship(back_populates="clinic")