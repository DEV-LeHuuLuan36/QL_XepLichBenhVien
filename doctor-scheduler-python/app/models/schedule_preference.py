from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.dialects.mssql import NVARCHAR # Thêm cho thống nhất
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from .doctor import Doctor
    from .shift import Shift

class SchedulePreference(Base):
    __tablename__ = "schedule_preferences"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"))
    day_of_week: Mapped[int] = mapped_column(Integer) 
    preference_score: Mapped[int] = mapped_column(Integer)
    
    doctor: Mapped["Doctor"] = relationship(back_populates="preferences")
    shift: Mapped["Shift"] = relationship(back_populates="preferences")

    def __repr__(self):
        # Sửa lỗi: Tham chiếu đến self.preference_score, không phải self.score
        return f"<SchedulePreference(id={self.id}, doc={self.doctor_id}, shift={self.shift_id}, day={self.day_of_week}, score={self.preference_score})>"