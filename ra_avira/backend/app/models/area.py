import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    city: Mapped[str] = mapped_column(String(100), default="Hyderabad")
    zone: Mapped[Optional[str]] = mapped_column(String(100))
    pin_codes: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    center_lat: Mapped[Optional[float]] = mapped_column(Float)
    center_lng: Mapped[Optional[float]] = mapped_column(Float)
    avg_price_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    appreciation_1y: Mapped[Optional[float]] = mapped_column(Float)
    appreciation_3y: Mapped[Optional[float]] = mapped_column(Float)
    appreciation_5y: Mapped[Optional[float]] = mapped_column(Float)
    rental_yield: Mapped[Optional[float]] = mapped_column(Float)
    metro_distance_km: Mapped[Optional[float]] = mapped_column(Float)
    upcoming_metro: Mapped[bool] = mapped_column(Boolean, default=False)
    flood_risk_score: Mapped[float] = mapped_column(Float, default=0)
    water_availability_score: Mapped[float] = mapped_column(Float, default=5)
    traffic_score: Mapped[float] = mapped_column(Float, default=5)
    infrastructure_score: Mapped[float] = mapped_column(Float, default=5)
    school_density: Mapped[int] = mapped_column(Integer, default=0)
    hospital_density: Mapped[int] = mapped_column(Integer, default=0)
    it_corridor_distance_km: Mapped[Optional[float]] = mapped_column(Float)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AreaPriceTrend(Base):
    __tablename__ = "area_price_trends"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("areas.id"))
    month: Mapped[date] = mapped_column(Date, nullable=False)
    avg_price_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    median_price_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    transaction_count: Mapped[Optional[int]] = mapped_column(Integer)
    rental_avg: Mapped[Optional[int]] = mapped_column(Integer)
    appreciation_pct: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    project_type: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(30))
    completion_date: Mapped[Optional[date]] = mapped_column(Date)
    affected_areas: Mapped[Optional[list]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    impact_radius_km: Mapped[Optional[float]] = mapped_column(Float)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    estimated_appreciation_pct: Mapped[Optional[float]] = mapped_column(Float)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
