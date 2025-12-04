from __future__ import annotations
from typing import List, TYPE_CHECKING
from sqlalchemy import Integer
from sqlalchemy.dialects.mssql import NVARCHAR 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base 

if TYPE_CHECKING:
    from .assignment import Assignment
    from .doctor import Doctor

class Clinic(Base):
    __tablename__ = "clinics"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    
    # --- MỚI: Cấu hình định biên nhân sự cho 1 ca trực ---
    required_main: Mapped[int] = mapped_column(Integer, default=2, nullable=False) # Mặc định 2 chính
    required_sub: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # Mặc định 1 phụ
    
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="clinic", lazy="selectin")
    # Danh sách bác sĩ thuộc biên chế khoa này
    doctors: Mapped[List["Doctor"]] = relationship(back_populates="clinic", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Clinic(id={self.id}, name='{self.name}')>"