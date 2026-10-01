import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Date, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Builder(Base):
    __tablename__ = "builders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    rera_ids: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    reputation_score: Mapped[float] = mapped_column(Float, default=0)
    total_projects: Mapped[int] = mapped_column(Integer, default=0)
    completed_projects: Mapped[int] = mapped_column(Integer, default=0)
    delayed_projects: Mapped[int] = mapped_column(Integer, default=0)
    complaints_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_delay_months: Mapped[float] = mapped_column(Float, default=0)
    legal_cases: Mapped[int] = mapped_column(Integer, default=0)
    established_year: Mapped[Optional[int]] = mapped_column(Integer)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReraProject(Base):
    __tablename__ = "rera_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rera_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    builder_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("builders.id"))
    area_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("areas.id"))
    status: Mapped[Optional[str]] = mapped_column(String(30))
    registration_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    total_units: Mapped[Optional[int]] = mapped_column(Integer)
    sold_units: Mapped[Optional[int]] = mapped_column(Integer)
    completion_percentage: Mapped[Optional[float]] = mapped_column(Float)
    complaints: Mapped[int] = mapped_column(Integer, default=0)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
