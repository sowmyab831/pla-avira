"""Database connection and session management."""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, Column, String, Float, Integer, DateTime, Boolean, JSON
from contextlib import asynccontextmanager
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Base class for ORM models
Base = declarative_base()


# Database Models
class PortfolioHoldingDB(Base):
    """Portfolio holding database model."""
    __tablename__ = "portfolio_holdings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False)
    shares = Column(Float, nullable=False)
    average_cost = Column(Float, nullable=False)
    purchase_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StockAlertDB(Base):
    """Stock alert database model."""
    __tablename__ = "stock_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False)
    alert_type = Column(String, nullable=False)  # price_above, price_below, percent_change
    target_value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    triggered_at = Column(DateTime, nullable=True)


class UploadedDocumentDB(Base):
    """Uploaded document tracking."""
    __tablename__ = "uploaded_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    document_type = Column(String, nullable=False)  # health, finance, etc.
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    summary = Column(String, nullable=True)
    doc_metadata = Column(String, nullable=True)  # JSON string


class ChatSessionDB(Base):
    """Chat session tracking for AI assistant."""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ChatMessageDB(Base):
    """Chat messages for AI assistant sessions."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    msg_metadata = Column(String, nullable=True)  # JSON string for additional data


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
    user_metadata = Column(JSON, nullable=True)


class UserFeatureSettingsDB(Base):
    """User feature toggle settings for mobile app."""
    __tablename__ = "user_feature_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, unique=True, index=True)
    # Feature toggles
    show_investing = Column(Boolean, default=True)
    show_travel = Column(Boolean, default=True)
    show_shopping = Column(Boolean, default=True)
    show_weather = Column(Boolean, default=True)
    show_health = Column(Boolean, default=True)
    show_calendar = Column(Boolean, default=True)
    show_tasks = Column(Boolean, default=True)
    show_grocery = Column(Boolean, default=True)
    show_documents = Column(Boolean, default=True)
    # Preferences
    default_currency = Column(String, default="USD")
    temperature_unit = Column(String, default="F")  # F or C
    theme = Column(String, default="dark")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentAnalysisDB(Base):
    """Analyzed documents (health reports, bank statements, etc)."""
    __tablename__ = "document_analyses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    document_type = Column(String, nullable=False)  # health, finance, receipt, other
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    ocr_text = Column(String, nullable=True)
    analysis_summary = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)  # Structured data from analysis
    confidence_score = Column(Float, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed


class SecureDocumentDB(Base):
    """
    UUID-tracked documents with privacy masking.
    Original content never leaves this table; only masked_text is sent to LLMs.
    """
    __tablename__ = "secure_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_uuid = Column(String, nullable=False, unique=True, index=True)
    user_uuid = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)  # finance, health, travel, shopping, legal, personal, other
    original_file_path = Column(String, nullable=True)  # encrypted on disk
    masked_text = Column(String, nullable=True)  # safe to send to LLM
    ocr_text_hash = Column(String, nullable=True)  # SHA-256 of raw OCR (never stored raw)
    analysis_result = Column(JSON, nullable=True)
    confidence_score = Column(Float, nullable=True)
    entity_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EntityMappingDB(Base):
    """
    Maps masked tokens back to real values.
    Stored locally — NEVER sent externally.
    
    Example:
        token="[PERSON_001]" → entity_type="PERSON", original_hash=sha256("John Smith")
    """
    __tablename__ = "entity_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_uuid = Column(String, nullable=False, index=True)
    user_uuid = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False)  # e.g. [PERSON_001], [SSN_001]
    entity_type = Column(String, nullable=False)  # PERSON, SSN, CREDIT_CARD, HOSPITAL, etc.
    original_hash = Column(String, nullable=False)  # SHA-256 of original value
    partial_reveal = Column(String, nullable=True)  # e.g. "J*** S***", "***-**-6789"
    position_start = Column(Integer, nullable=True)
    position_end = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetTokenDB(Base):
    """Password reset tokens — persisted so they survive pod restarts."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PriceSnapshotDB(Base):
    """Shopping price snapshot — written on every product search (own tracker)."""
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_key = Column(String, nullable=False, index=True)  # normalized title|retailer
    retailer = Column(String, nullable=False)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    url = Column(String, nullable=True)
    source = Column(String, default="search")  # search | refresh | estimate
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)


class FareSnapshotDB(Base):
    """Flight fare snapshot — written on every flight search."""
    __tablename__ = "fare_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route = Column(String, nullable=False, index=True)  # e.g. CLT-RDU
    travel_date = Column(String, nullable=True)
    carrier = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    source = Column(String, default="search")
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)


class MaintenanceItemDB(Base):
    """User's maintenance checklist item state (home/vehicle/appliance)."""
    __tablename__ = "maintenance_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    template_id = Column(String, nullable=True)  # link to seeded template task
    category = Column(String, nullable=False)    # home | vehicle | appliance
    season = Column(String, nullable=True)       # spring/summer/fall/winter/monthly
    task_name = Column(String, nullable=False)
    interval_months = Column(Integer, nullable=True)
    last_done = Column(DateTime, nullable=True)
    next_due = Column(DateTime, nullable=True)
    status = Column(String, default="pending")   # pending | done | snoozed
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApplianceDB(Base):
    """Appliance registry for lifespan and warranty tracking."""
    __tablename__ = "appliances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    appliance_type = Column(String, nullable=False)  # water_heater, hvac, fridge...
    brand = Column(String, nullable=True)
    purchase_date = Column(DateTime, nullable=True)
    warranty_end = Column(DateTime, nullable=True)
    expected_lifespan_years = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RepairLogDB(Base):
    """Repair history log."""
    __tablename__ = "repair_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)  # home | vehicle | appliance
    issue = Column(String, nullable=False)
    repair_date = Column(DateTime, nullable=True)
    cost = Column(Float, nullable=True)
    contractor = Column(String, nullable=True)
    document_id = Column(String, nullable=True)  # link to uploaded receipt
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


async def get_session():
    """Dependency for FastAPI to get database session."""
    async with async_session_maker() as session:
        yield session


def get_db():
    """Synchronous database session for compatibility."""
    # For now, return None and use in-memory storage as fallback
    # TODO: Implement proper sync session or migrate all routes to async
    return None


async def init_db():
    """Initialize database (create tables, run migrations)."""
    # Import model modules so their tables are registered on Base.metadata.
    import app.models.nexus  # noqa: F401
    import app.models.life_admin  # noqa: F401
    import app.models.ai  # noqa: F401
    import app.models.task  # noqa: F401
    import app.models.ops  # noqa: F401
    async with engine.begin() as conn:
        # For production, use Alembic migrations
        # For now, just create tables from declarative models
        await conn.run_sync(Base.metadata.create_all)

        # Inline migration: add subscription columns if missing
        try:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR DEFAULT 'free'"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR"
            ))
        except Exception as e:
            logger.debug(f"Migration note (safe to ignore): {e}")

        # R3: family member lifecycle column
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active'"
            ))
        except Exception as e:
            logger.debug(f"Migration note (safe to ignore): {e}")

    logger.info("Database initialized")


async def health_check_db() -> bool:
    """Check database connectivity."""
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@asynccontextmanager
async def get_db_context():
    """Context manager for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
