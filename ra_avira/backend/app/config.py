from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "RA Avira"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET: str = "jwt-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 72

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ra_user:ra_secure_pass_2024@localhost:5432/ra_avira"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenSearch
    OPENSEARCH_URL: str = "http://localhost:9200"

    # AI
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Maps
    GOOGLE_MAPS_API_KEY: Optional[str] = None

    # Voice
    DEEPGRAM_API_KEY: Optional[str] = None
    ELEVENLABS_API_KEY: Optional[str] = None

    # Social Media
    YOUTUBE_API_KEY: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None

    # WhatsApp
    WHATSAPP_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_ID: Optional[str] = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Crawling
    CRAWL_INTERVAL_MINUTES: int = 60
    MAX_CONCURRENT_CRAWLERS: int = 5

    # Hyderabad-specific
    CITY: str = "Hyderabad"
    STATE: str = "Telangana"
    STAMP_DUTY_PCT: float = 5.0
    REGISTRATION_PCT: float = 0.5
    GST_UNDER_CONSTRUCTION_PCT: float = 5.0
    BROKERAGE_PCT: float = 2.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
