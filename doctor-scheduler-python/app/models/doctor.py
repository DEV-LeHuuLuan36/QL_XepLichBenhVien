from __future__ import annotations
from typing import List, TYPE_CHECKING
import enum
from sqlalchemy import Integer, ForeignKey, Enum as SqEnum
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from .assignment import Assignment
    from .leave_request import LeaveRequest
    from .schedule_preference import SchedulePreference
    from .clinic import Clinic

# Định nghĩa Enum cho vai trò
class DoctorRole(enum.Enum):
    MAIN = "Chính"
    SUB = "Phụ"

class Doctor(Base):
    __tablename__ = "doctors"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    specialty: Mapped[str] = mapped_column(NVARCHAR(100))
    
    # --- MỚI: Phân loại vai trò bác sĩ ---
    role: Mapped[DoctorRole] = mapped_column(
        SqEnum(DoctorRole, native_enum=False), 
        default=DoctorRole.SUB,
        nullable=False
    )
    
    # --- MỚI: Bác sĩ thuộc về Khoa nào (Home Department) ---
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), nullable=True)

    total_shifts_worked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Quan hệ
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="doctor", lazy="selectin")
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(back_populates="doctor", lazy="selectin")
    preferences: Mapped[List["SchedulePreference"]] = relationship(back_populates="doctor", lazy="selectin")
    
    # Quan hệ với Khoa chủ quản
    clinic: Mapped["Clinic"] = relationship(back_populates="doctors")

    def __repr__(self) -> str:
        return f"<Doctor(id={self.id}, name='{self.name}', role='{self.role.value}')>"