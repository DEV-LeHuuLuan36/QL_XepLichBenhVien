from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Date, ForeignKey
from sqlalchemy.dialects.mssql import NVARCHAR # Dùng NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime
from app.models.base import Base

if TYPE_CHECKING:
    from .doctor import Doctor

class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False) 
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(NVARCHAR(255)) # Dùng NVARCHAR
    status: Mapped[str] = mapped_column(NVARCHAR(50), default="Pending", nullable=False) # Dùng NVARCHAR
    
    doctor: Mapped["Doctor"] = relationship(back_populates="leave_requests")

    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, doctor_id={self.doctor_id}, date={self.date})>"