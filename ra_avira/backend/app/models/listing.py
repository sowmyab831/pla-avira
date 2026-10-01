import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Boolean, DateTime, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RawListing(Base):
    __tablename__ = "raw_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_listing_id: Mapped[Optional[str]] = mapped_column(String(255))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id"))
    duplicate_of: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_listings.id"))
    images_hash: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    crawled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SocialMediaSource(Base):
    __tablename__ = "social_media_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(30))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(255))
    author: Mapped[Optional[str]] = mapped_column(String(255))
    content: Mapped[Optional[str]] = mapped_column(Text)
    transcription: Mapped[Optional[str]] = mapped_column(Text)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id"))
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    urgency_score: Mapped[Optional[float]] = mapped_column(Float)
    fake_probability: Mapped[float] = mapped_column(Float, default=0)
    media_urls: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    crawled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
