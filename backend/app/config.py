from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, List
import os
import json


class Settings(BaseSettings):
    """Application configuration from environment variables.
    
    Supports two deployment modes:
    1. Local Mac: Backend runs locally with GPU, K8s services via localhost
    2. K8s: Everything runs in Kubernetes
    """
    
    # Deployment mode: "local" (Mac + K8s) or "kubernetes"
    deployment_mode: str = Field(default="kubernetes", env="DEPLOYMENT_MODE")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # Security — MUST be overridden via SECRET_KEY env in production
    secret_key: str = Field(
        default="dev-only-secret-change-in-production",
        env="SECRET_KEY"
    )

    # Upload limits (bytes) — reject oversized files before parsing
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, env="MAX_UPLOAD_BYTES")
    cors_origins_str: str = Field(default="http://localhost:3000,http://localhost:5173", env="CORS_ORIGINS")
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if isinstance(self.cors_origins_str, str):
            return [origin.strip() for origin in self.cors_origins_str.split(',')]
        return self.cors_origins_str if isinstance(self.cors_origins_str, list) else ["http://localhost:3000", "http://localhost:5173"]
    
    # Database
    database_url: str = Field(
        default="postgresql://pla_user:changeme@localhost:5432/pla_db",
        env="DATABASE_URL"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    
    # Vector DB (Qdrant)
    qdrant_url: str = Field(
        default="http://localhost:6333",
        env="QDRANT_URL"
    )
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    
    # Search (MeiliSearch)
    meili_url: str = Field(
        default="http://localhost:7700",
        env="MEILI_URL"
    )
    meili_master_key: str = Field(
        default="changeme-meili-master-key",
        env="MEILI_MASTER_KEY"
    )
    
    # Local LLM (Ollama) - use host.docker.internal for Kubernetes pod access
    ollama_host: str = Field(
        default="http://localhost:11434",
        env="OLLAMA_HOST"
    )

    # ── Multi-model routing ──────────────────────────────────────
    # M4 16GB → ~11GB GPU budget. Models under 10GB get 100% Metal GPU.
    #
    # FINANCE model: qwen2.5:14b (9.3GB, 100% GPU, 18.8 tok/s)
    #   Best for: stock analysis, forecasting synthesis, earnings analysis,
    #   structured data reasoning, numerical analysis.
    #
    # FAST model: mistral:7b-instruct (4.4GB, 100% GPU, 37 tok/s)
    #   Best for: email extraction, shopping queries, travel planning,
    #   calendar parsing, quick classification, conversational assistant.
    #
    # DEEP model: qwen3:14b (9.3GB, 100% GPU, ~18 tok/s with thinking mode)
    #   Best for: on-demand deep reasoning when quality > speed.
    #   Hybrid thinking model - reasons step-by-step before answering.
    #   Fully fits M4 16GB GPU budget (unlike 32B models at ~5 tok/s).
    #
    ollama_model: str = Field(
        default="qwen3:14b",
        env="OLLAMA_MODEL"
    )
    ollama_finance_model: str = Field(
        default="qwen2.5:14b",
        env="OLLAMA_FINANCE_MODEL"
    )
    ollama_fast_model: str = Field(
        default="mistral:7b-instruct",
        env="OLLAMA_FAST_MODEL"
    )
    ollama_deep_model: str = Field(
        default="qwen3:14b",
        env="OLLAMA_DEEP_MODEL"
    )
    ollama_fallback_models: str = Field(
        default="mistral:7b-instruct,qwen2.5:14b",
        env="OLLAMA_FALLBACK_MODELS"
    )
    ollama_timeout: int = Field(
        default=120,
        env="OLLAMA_TIMEOUT"
    )
    
    def model_for_task(self, task: str) -> str:
        """Select the optimal model for a given task type.
        
        Task types: 'finance', 'fast', 'deep', or default.
        """
        task_map = {
            "finance": self.ollama_finance_model,    # stock analysis, forecasting
            "stock": self.ollama_finance_model,
            "analysis": self.ollama_finance_model,
            "fast": self.ollama_fast_model,          # email, shopping, travel, calendar
            "email": self.ollama_fast_model,
            "shopping": self.ollama_fast_model,
            "travel": self.ollama_fast_model,
            "calendar": self.ollama_fast_model,
            "assistant": self.ollama_fast_model,
            "deep": self.ollama_deep_model,          # deep reasoning (on-demand)
            "reasoning": self.ollama_deep_model,
        }
        return task_map.get(task, self.ollama_model)

    @property
    def available_models(self) -> list:
        """List of available Ollama models (sorted by GPU-fit preference for M4 16GB)."""
        return ["qwen3:14b", "qwen2.5:14b", "mistral:7b-instruct"]
    
    @property
    def fallback_models(self) -> list:
        """Parse fallback models from comma-separated string."""
        return [m.strip() for m in self.ollama_fallback_models.split(',')]
    
    # ── Feature flags (Release 0) ─────────────────────────────────
    # All default to the safe/local behaviour. Flip explicitly per deployment.
    ai_gateway_enabled: bool = Field(default=True, env="AVIRA_AI_GATEWAY")
    ai_model_settings_enabled: bool = Field(default=True, env="AVIRA_AI_MODEL_SETTINGS")
    ai_cloud_enabled: bool = Field(default=False, env="AVIRA_AI_CLOUD")
    ai_byok_enabled: bool = Field(default=False, env="AVIRA_AI_BYOK")
    # Autonomous trading loops are OFF by default and real-money orders are
    # never placed from a background task regardless of this flag.
    auto_trading_enabled: bool = Field(default=False, env="AVIRA_AUTO_TRADING")
    payments_live_enabled: bool = Field(default=False, env="AVIRA_PAYMENTS_LIVE")

    # External LLMs (optional; only used through the AI gateway when
    # AVIRA_AI_CLOUD is on and the user/tenant policy permits cloud processing)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    moonshot_api_key: Optional[str] = Field(default=None, env="MOONSHOT_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")
    xai_api_key: Optional[str] = Field(default=None, env="XAI_API_KEY")
    mistral_api_key: Optional[str] = Field(default=None, env="MISTRAL_API_KEY")
    # Admin-allowlisted OpenAI-compatible endpoints: "name=https://host/v1,..."
    ai_compat_endpoints: str = Field(default="", env="AVIRA_AI_COMPAT_ENDPOINTS")

    # Telegram bot (inbound chat + outbound alerts). Token from @BotFather.
    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    # Default chat id to deliver alerts to (auto-captured on first /start if unset).
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")
    # Optional: shared secret for the inbound webhook. Set the same value as
    # `secret_token` in Telegram's setWebhook; requests without it are rejected.
    telegram_webhook_secret: Optional[str] = Field(default=None, env="TELEGRAM_WEBHOOK_SECRET")
    # Master switch for the background scheduler (alerts, tips, inbound polling).
    scheduler_enabled: bool = Field(default=True, env="SCHEDULER_ENABLED")
    
    # Voice: STT via local Whisper (transformers), TTS via ElevenLabs (optional) else browser.
    whisper_model: str = Field(default="openai/whisper-base.en", env="WHISPER_MODEL")
    elevenlabs_api_key: Optional[str] = Field(default=None, env="ELEVENLABS_API_KEY")
    # Default: a British female voice id on ElevenLabs' free library ("Alice"). Override per deployment.
    elevenlabs_voice_id: str = Field(default="Xb7hH8MSUJpSbSDYk0k2", env="ELEVENLABS_VOICE_ID")
    # Key used to encrypt IMAP app passwords at rest (derive from a long random string).
    avira_vault_key: Optional[str] = Field(default=None, env="AVIRA_VAULT_KEY")

    # MinIO (local object storage)
    minio_endpoint: str = Field(
        default="localhost:9000",
        env="MINIO_ENDPOINT"
    )
    minio_access_key: str = Field(
        default="minioadmin",
        env="MINIO_ACCESS_KEY"
    )
    minio_secret_key: str = Field(
        default="minioadmin",
        env="MINIO_SECRET_KEY"
    )
    minio_bucket: str = Field(
        default="documents",
        env="MINIO_BUCKET"
    )
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
