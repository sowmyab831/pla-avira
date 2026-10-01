"""
User and RBAC Models
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from datetime import datetime
from app.database import Base


class UserDB(Base):
    """User model with role-based access control."""
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # admin, user
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(String, nullable=False, default="free")  # free, premium, enterprise
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, nullable=True)
