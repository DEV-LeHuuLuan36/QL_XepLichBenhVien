from __future__ import annotations
from typing import List, TYPE_CHECKING
from sqlalchemy import Time, Integer 
from sqlalchemy.dialects.mssql import NVARCHAR # Dùng NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime
from app.models.base import Base 

if TYPE_CHECKING:
    from .assignment import Assignment
    from .schedule_preference import SchedulePreference

class Shift(Base):
    __tablename__ = "shifts"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False) # Dùng NVARCHAR
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="shift", lazy="selectin")
    preferences: Mapped[List["SchedulePreference"]] = relationship(back_populates="shift", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Shift(id={self.id}, name='{self.name}')>"