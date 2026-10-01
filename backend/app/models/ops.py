"""Release 2–4 data models: assistant memory, durable jobs, tracked products.

Kept in one module so init_db registers them together; each table is also
covered by a matching SQL file in backend/migrations/ for existing databases.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Boolean, BigInteger, Index

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class MemoryItemDB(Base):
    """User-scoped long-term memory for the assistant.

    kind: note | fact | preference | event. `pinned` memories always rank first
    in recall. `source` records how the memory was captured (chat, manual, doc).
    """
    __tablename__ = "memory_items"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    kind = Column(String(32), nullable=False, default="note")
    text = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)                    # ["school", "visa"]
    source = Column(String(32), nullable=False, default="manual")
    pinned = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobDB(Base):
    """Durable job queue — survives process restarts.

    status transitions: pending → claimed → done | failed | dead.
    A claimed job whose lock expires returns to pending (crash recovery).
    `dedupe_key` makes enqueue idempotent when set.
    """
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    kind = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="pending", index=True)
    run_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    locked_by = Column(String(64), nullable=True)
    locked_at = Column(DateTime, nullable=True)
    dedupe_key = Column(String(128), nullable=True, unique=True)
    result = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_jobs_status_run_at", "status", "run_at"),)


class TrackedProductDB(Base):
    """A product the user wants price alerts for (R4 shopping lifecycle)."""
    __tablename__ = "tracked_products"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    product_key = Column(String(256), nullable=False, index=True)  # price_tracker key
    title = Column(String(300), nullable=False)
    retailer = Column(String(120), nullable=True)
    url = Column(Text, nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    target_minor = Column(BigInteger, nullable=True)      # alert when price <= target
    drop_pct = Column(Integer, nullable=False, default=10)  # or dropped >= N% vs first seen
    baseline_minor = Column(BigInteger, nullable=True)    # price when tracked
    last_minor = Column(BigInteger, nullable=True)        # latest observed
    active = Column(Boolean, nullable=False, default=True)
    last_alerted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_tracked_user_key", "user_id", "product_key", unique=True),)
