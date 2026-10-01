"""Owned household commitments and payment records; additive tables only."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Date, DateTime, Text, JSON, UniqueConstraint
from app.database import Base


def new_id():
    return str(uuid.uuid4())


class CommitmentDB(Base):
    __tablename__ = "life_commitments"
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String(180), nullable=False)
    kind = Column(String, nullable=False)
    country = Column(String(2), nullable=False)
    currency = Column(String(3), nullable=False)
    amount_minor = Column(BigInteger, nullable=True)
    due_date = Column(Date, nullable=False, index=True)
    timezone = Column(String, nullable=False)
    recurrence = Column(String, nullable=False, default="none")
    anchor_day = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="open")
    notes = Column(Text, nullable=False, default="")
    reference_url = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    history = Column(JSON, nullable=False, default=list)


class BillingAccountDB(Base):
    __tablename__ = "billing_accounts"
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=False)
    country = Column(String, nullable=False)
    tier = Column(String, nullable=False)
    provider_id = Column(String, nullable=True, unique=True)
    checkout_id = Column(String, nullable=True)
    checkout_url = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="creating")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BillingEventDB(Base):
    __tablename__ = "billing_events"
    __table_args__ = (UniqueConstraint("provider", "event_id"),)
    id = Column(String, primary_key=True, default=new_id)
    provider = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OwnedWishlistDB(Base):
    __tablename__ = "owned_wishlist"
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    target_minor = Column(BigInteger, nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
