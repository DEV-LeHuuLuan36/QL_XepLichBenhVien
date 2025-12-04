from __future__ import annotations
from typing import List
from sqlalchemy import (
    DateTime, func, Integer, Enum, Date 
)
from sqlalchemy.dialects.mssql import NVARCHAR # Dùng NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base 
import enum
import datetime 

class JobStatus(enum.Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"

class SchedulingJob(Base):
    __tablename__ = "scheduling_jobs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False) # Dùng NVARCHAR
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, 
             values_callable=lambda obj: [e.value for e in obj],
             native_enum=False), # Bắt buộc DB dùng string
        default=JobStatus.PENDING,
        nullable=False
    )
    
    status_message: Mapped[str | None] = mapped_column(NVARCHAR(1000)) # Dùng NVARCHAR
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="scheduling_job")
    
    def __repr__(self):
        status_val = self.status.value if isinstance(self.status, enum.Enum) else self.status
        return f"<SchedulingJob(id={self.id}, name='{self.name}', status='{status_val}')>"