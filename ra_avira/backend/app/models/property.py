import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, DateTime, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(500))
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active")

    # Location
    area_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("areas.id"))
    address: Mapped[Optional[str]] = mapped_column(Text)
    landmark: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    pin_code: Mapped[Optional[str]] = mapped_column(String(10))

    # Pricing
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_per_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    registration_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    market_value_estimate: Mapped[Optional[int]] = mapped_column(BigInteger)
    negotiable: Mapped[bool] = mapped_column(Boolean, default=True)

    # Specifications
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer)
    balconies: Mapped[Optional[int]] = mapped_column(Integer)
    total_area_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    carpet_area_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    super_buildup_area_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer)
    facing: Mapped[Optional[str]] = mapped_column(String(20))
    age_years: Mapped[Optional[int]] = mapped_column(Integer)
    possession_status: Mapped[Optional[str]] = mapped_column(String(30))
    possession_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    furnishing: Mapped[Optional[str]] = mapped_column(String(20))
    parking_count: Mapped[int] = mapped_column(Integer, default=0)

    # Builder
    builder_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("builders.id"))
    project_name: Mapped[Optional[str]] = mapped_column(String(255))
    rera_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Scores
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    value_score: Mapped[float] = mapped_column(Float, default=0)
    legal_score: Mapped[float] = mapped_column(Float, default=0)
    location_score: Mapped[float] = mapped_column(Float, default=0)
    builder_score: Mapped[float] = mapped_column(Float, default=0)
    fraud_probability: Mapped[float] = mapped_column(Float, default=0)

    # Amenities
    amenities: Mapped[Optional[list]] = mapped_column(ARRAY(Text))

    # Source
    source: Mapped[Optional[str]] = mapped_column(String(50))
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    source_listing_id: Mapped[Optional[str]] = mapped_column(String(255))

    # AI
    embedding = mapped_column(Vector(1536), nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    ai_highlights: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    ai_concerns: Mapped[Optional[list]] = mapped_column(ARRAY(Text))

    # Media
    images: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    floor_plan_url: Mapped[Optional[str]] = mapped_column(Text)
    video_url: Mapped[Optional[str]] = mapped_column(Text)
    virtual_tour_url: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    price_history: Mapped[List["PriceHistory"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    cost_breakdown: Mapped[Optional["CostBreakdown"]] = relationship(back_populates="property", uselist=False)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"))
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_per_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[Optional[str]] = mapped_column(String(50))

    property: Mapped["Property"] = relationship(back_populates="price_history")


class CostBreakdown(Base):
    __tablename__ = "cost_breakdowns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"))
    base_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    registration_charges: Mapped[Optional[int]] = mapped_column(BigInteger)
    stamp_duty: Mapped[Optional[int]] = mapped_column(BigInteger)
    gst: Mapped[Optional[int]] = mapped_column(BigInteger)
    brokerage: Mapped[Optional[int]] = mapped_column(BigInteger)
    parking_charges: Mapped[Optional[int]] = mapped_column(BigInteger)
    clubhouse_charges: Mapped[Optional[int]] = mapped_column(BigInteger)
    corpus_fund: Mapped[Optional[int]] = mapped_column(BigInteger)
    maintenance_deposit: Mapped[Optional[int]] = mapped_column(BigInteger)
    interior_estimate: Mapped[Optional[int]] = mapped_column(BigInteger)
    loan_processing_fee: Mapped[Optional[int]] = mapped_column(BigInteger)
    legal_verification: Mapped[Optional[int]] = mapped_column(BigInteger)
    furnishing_estimate: Mapped[Optional[int]] = mapped_column(BigInteger)
    hidden_charges: Mapped[Optional[int]] = mapped_column(BigInteger)
    total_ownership_cost: Mapped[Optional[int]] = mapped_column(BigInteger)
    monthly_emi_estimate: Mapped[Optional[int]] = mapped_column(BigInteger)
    monthly_maintenance: Mapped[Optional[int]] = mapped_column(BigInteger)
    notes: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    property: Mapped["Property"] = relationship(back_populates="cost_breakdown")
