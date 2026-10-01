"""FastAPI main application with privacy, search, and LLM integration."""
import logging
import sys
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.database import init_db, health_check_db, get_session
from app.search import get_indexer
from app.router_ai import router as ai_router
from app.router_integrations import router as integrations_router
from app.router_school_calendar import router as school_calendar_router
from app.routes.finance import router as finance_router
from app.routes.health import router as health_router
from app.routes.school import router as school_router
from app.routes.home import router as home_router
from app.routes.bills import router as bills_router
from app.router_assistant import router as assistant_router
from app.routes.shopping import router as shopping_router
from app.routes.travel import router as travel_router
from app.routes.grocery import router as grocery_router
from app.routes.family import router as family_router
from app.routes.portfolio import router as portfolio_router
from app.routes.tasks import router as tasks_router
from app.routes.nutrition import router as nutrition_router
from app.routes.wellness import router as wellness_router
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.user_settings import router as user_settings_router
from app.routes.subscription import router as subscription_router
from app.routes.news import router as news_router
from app.routes.market_intel import router as market_intel_router
from app.routes.forecast import router as forecast_router
from app.routes.trading import router as trading_router
from app.routes.earnings import router as earnings_router
from app.routes.notifications import router as notifications_router
from app.routes.public_market import router as public_market_router
from app.routes.telegram import router as telegram_router
from app.routes.nexus import router as nexus_router
from app.routes.radar import router as radar_router
from app.routes.care import router as care_router
from app.routes.pantry import router as pantry_router
from app.routes.family_hub import router as family_hub_router
from app.routes.voice import router as voice_router
from app.routes.maintenance import router as maintenance_router
from app.routes.life_admin import router as life_admin_router
from app.routes.billing import router as billing_router
from app.routes.ai_settings import router as ai_settings_router
from app.routes.memory import router as memory_router

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    """Health check response."""
    status: str
    postgres: bool
    redis: bool
    qdrant: bool
    meili: bool
    ollama: bool
    environment: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    logger.info("Starting Personal Life Assistant backend...")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Probe local models so the catalog can say truthfully what is installed
    try:
        from app.ai.providers import adapter_for
        from app.ai.registry import get_registry
        from app.ai.credentials import platform_credential
        names = await adapter_for("ollama").list_models(platform_credential("ollama"), timeout_s=3)
        get_registry().set_installed_local(names)
        logger.info("AI gateway: %d local model(s) installed", len(names))
    except Exception as e:
        logger.warning(f"AI gateway local probe failed: {e}")

    # Register durable-job handlers before the scheduler starts claiming work
    try:
        import app.services.job_handlers  # noqa: F401
        logger.info("Job queue handlers registered")
    except Exception as e:
        logger.error(f"Job handler registration failed: {e}")

    # Start background scheduler (Telegram alerts, day-trade tips, inbound chat)
    try:
        from app.services import scheduler
        scheduler.start()
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")

    yield
    
    # Shutdown
    logger.info("Shutting down...")
    try:
        from app.services import scheduler
        await scheduler.stop()
    except Exception as e:
        logger.error(f"Scheduler stop failed: {e}")
    indexer = get_indexer()
    await indexer.close()


# Create FastAPI app
app = FastAPI(
    title="Personal Life Assistant API",
    description="Production-capable local-first microservices stack",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - restrict to configured origins in production
_cors_origins = settings.cors_origins if settings.environment == "production" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for large JSON payloads (news feeds, portfolio data)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ── Rate limiting (in-memory sliding window, no external deps) ────────────────
_RATE_LIMIT = 300           # requests per window per client
_RATE_WINDOW = 60.0         # seconds
_rate_buckets: dict = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[client_ip]
    while bucket and now - bucket[0] > _RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again shortly."},
            headers={"Retry-After": "10"},
        )
    bucket.append(now)
    return await call_next(request)


# ── Actor context + auth gate ────────────────────────────────────────────────
# Decode the Bearer token (signature + expiry only, no DB) and publish the
# principal on a contextvar so LLM/gateway calls are attributable. Any /api/*
# route not in _PUBLIC_PREFIXES requires a valid token; endpoint-level
# Depends(get_current_user) still does the DB-backed authorization checks.
_PUBLIC_PREFIXES = (
    "/api/auth/",               # login, signup, init-admin, password reset
    "/api/public/",             # public market data
    "/api/telegram/webhook",    # Telegram servers; no user JWT exists there
    "/api/billing/webhook",     # Stripe/Razorpay; signature-verified in handler
)


@app.middleware("http")
async def actor_context_middleware(request: Request, call_next):
    from app.services.llm_client import set_actor, current_actor
    token = None
    payload = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            import jwt as _jwt
            from app.routes.auth import SECRET_KEY, ALGORITHM
            payload = _jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])
            token = set_actor(payload.get("sub"), payload.get("tenant_id"), payload.get("role", "user"))
        except Exception:
            token = None

    path = request.url.path
    if (
        payload is None
        and request.method != "OPTIONS"
        and path.startswith("/api/")
        and not any(path.startswith(p) for p in _PUBLIC_PREFIXES)
    ):
        detail = "Not authenticated" if not auth else "Invalid or expired token"
        return JSONResponse(status_code=401, content={"detail": detail})
    try:
        return await call_next(request)
    finally:
        if token is not None:
            current_actor.reset(token)


# ── Request ID + timing + security headers ────────────────────────────────────
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    try:
        from app.services import telemetry
        telemetry.record(request.method, request.url.path, response.status_code, elapsed_ms)
    except Exception:
        pass  # telemetry must never break a request
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if elapsed_ms > 2000:
        logger.warning(f"SLOW REQUEST [{request_id}] {request.method} {request.url.path} took {elapsed_ms:.0f}ms")
    return response


# ── Fast probes for Kubernetes (no downstream calls) ──────────────────────────
@app.get("/health/live")
async def liveness():
    """Liveness probe: process is up. Never touches dependencies."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """Readiness probe: DB reachable (cheapest meaningful check)."""
    postgres_ok = await health_check_db()
    if not postgres_ok:
        return JSONResponse(status_code=503, content={"status": "not_ready", "postgres": False})
    return {"status": "ready", "postgres": True}


# Cached full health result (avoid hammering all services on every probe)
_health_cache: dict = {"result": None, "ts": 0.0}
_HEALTH_CACHE_TTL = 10.0


# Health check endpoint
@app.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Comprehensive health check for all services.
    
    Returns status of:
    - PostgreSQL database
    - Redis cache
    - Qdrant vector DB
    - MeiliSearch
    - Ollama LLM
    """
    now = time.monotonic()
    if _health_cache["result"] is not None and now - _health_cache["ts"] < _HEALTH_CACHE_TTL:
        return _health_cache["result"]

    postgres_ok = await health_check_db()
    
    # Check other services (simplified)
    redis_ok = True
    qdrant_ok = True
    meili_ok = True
    ollama_ok = True
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check Redis
            try:
                # Redis health check would go here
                pass
            except:
                redis_ok = False
            
            # Check Qdrant
            try:
                resp = await client.get(f"{settings.qdrant_url}/")
                qdrant_ok = resp.status_code == 200
            except:
                qdrant_ok = False
            
            # Check MeiliSearch
            try:
                resp = await client.get(f"{settings.meili_url}/health")
                meili_ok = resp.status_code == 200
            except:
                meili_ok = False
            
            # Check Ollama
            try:
                resp = await client.get(f"{settings.ollama_host}")
                ollama_ok = resp.status_code == 200
            except:
                ollama_ok = False
    except Exception as e:
        logger.warning(f"Health check error: {e}")
    
    overall_status = "healthy" if all([postgres_ok, redis_ok, qdrant_ok, meili_ok, ollama_ok]) else "degraded"
    
    result = HealthStatus(
        status=overall_status,
        postgres=postgres_ok,
        redis=redis_ok,
        qdrant=qdrant_ok,
        meili=meili_ok,
        ollama=ollama_ok,
        environment=settings.environment,
    )
    _health_cache["result"] = result
    _health_cache["ts"] = now
    return result


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "Personal Life Assistant API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include routers
app.include_router(ai_router)
app.include_router(integrations_router)
app.include_router(school_calendar_router)
app.include_router(finance_router)
app.include_router(health_router)
app.include_router(school_router)
app.include_router(home_router)
app.include_router(bills_router)
app.include_router(assistant_router)
app.include_router(shopping_router)
app.include_router(travel_router)
app.include_router(grocery_router)
app.include_router(family_router)
app.include_router(portfolio_router)
app.include_router(tasks_router)
app.include_router(nutrition_router)
app.include_router(wellness_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(user_settings_router)
app.include_router(subscription_router)
app.include_router(news_router)
app.include_router(market_intel_router)
app.include_router(forecast_router)
app.include_router(trading_router)
app.include_router(earnings_router)
app.include_router(notifications_router)
app.include_router(public_market_router)
app.include_router(telegram_router)
app.include_router(nexus_router)
app.include_router(radar_router)
app.include_router(care_router)
app.include_router(pantry_router)
app.include_router(family_hub_router)
app.include_router(voice_router)
app.include_router(maintenance_router)
app.include_router(life_admin_router)
app.include_router(billing_router)
app.include_router(ai_settings_router)
app.include_router(memory_router)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for logging."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
