from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime
from sqlalchemy.dialects.mssql import NVARCHAR
from app.models.base import Base # Import Base

if TYPE_CHECKING:
    from .doctor import Doctor
    from .clinic import Clinic
    from .shift import Shift
    from .scheduling_job import SchedulingJob

class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Ngày được phân công
    assignment_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    # --- Khóa ngoại (Foreign Keys)  ---
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), nullable=False)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("scheduling_jobs.id"), nullable=False) # <<< DÒNG QUAN TRỌNG
    # --- Kết thúc Khóa ngoại ---

    # --- Quan hệ (Relationships) ---
    doctor: Mapped["Doctor"] = relationship(back_populates="assignments", lazy="joined")
    clinic: Mapped["Clinic"] = relationship(back_populates="assignments", lazy="joined")
    shift: Mapped["Shift"] = relationship(back_populates="assignments", lazy="joined")
    scheduling_job: Mapped["SchedulingJob"] = relationship(back_populates="assignments", lazy="joined") # lazy='joined' tải kèm luôn job

    def __repr__(self):
        doc_name = self.doctor.name if self.doctor else f"ID:{self.doctor_id}"
        return f"<Assignment(id={self.id}, date={self.assignment_date}, doc='{doc_name}', job={self.job_id})>"