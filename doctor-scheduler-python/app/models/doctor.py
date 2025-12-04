from __future__ import annotations 
from typing import List, TYPE_CHECKING
from sqlalchemy import Integer 
from sqlalchemy.dialects.mssql import NVARCHAR # Dùng NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base 

if TYPE_CHECKING:
    from .assignment import Assignment
    from .leave_request import LeaveRequest
    from .schedule_preference import SchedulePreference

class Doctor(Base):
    __tablename__ = "doctors"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False) # Dùng NVARCHAR
    specialty: Mapped[str] = mapped_column(NVARCHAR(100)) # Dùng NVARCHAR
    total_shifts_worked: Mapped[int] = mapped_column(Integer, default=0, nullable=False) 
    
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="doctor", lazy="selectin")
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(back_populates="doctor", lazy="selectin")
    preferences: Mapped[List["SchedulePreference"]] = relationship(back_populates="doctor", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Doctor(id={self.id}, name='{self.name}')>"