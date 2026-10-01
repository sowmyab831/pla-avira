"""
Route smoke tests using FastAPI's TestClient. Verifies every new route
registers and returns 200 with expected top-level keys.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Avoid touching DB/Postgres during route registration
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.main import app  # noqa: E402
from app.routes.auth import create_access_token  # noqa: E402

client = TestClient(app)
# Private /api/* routes require a Bearer token (signature + expiry checked at
# the middleware gate). The smoke user doesn't need to exist in a DB because
# these endpoints don't call get_current_user.
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'smoke', 'role': 'user'})}"


@pytest.fixture(scope="module")
def db_available():
    """Some routes query Postgres directly; skip cleanly when it is down."""
    import socket
    from urllib.parse import urlparse
    from app.config import settings
    parsed = urlparse(settings.database_url.replace("+asyncpg", "").replace("+psycopg2", ""))
    try:
        socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), timeout=1).close()
        return True
    except OSError:
        return False


@pytest.mark.parametrize(
    "path",
    [
        "/api/market-intel/overview",
        "/api/market-intel/ai-boom",
        "/api/market-intel/influencers?limit_per=1",
        "/api/market-intel/geopolitics",
        "/api/market-intel/big-money",
        "/api/market-intel/tech-breakthroughs",
        "/api/market-intel/resources",
    ],
)
def test_market_intel_routes_200(path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), dict)


def test_market_intel_snapshot_has_expected_blocks():
    r = client.get("/api/market-intel/snapshot")
    assert r.status_code == 200
    body = r.json()
    for k in ("market_overview", "ai_boom", "influencers", "geopolitics"):
        assert k in body


def test_forecast_models_used_lists_local_models():
    r = client.get("/api/forecast/models-used")
    assert r.status_code == 200
    body = r.json()
    assert "llms" in body and "ml_models" in body and "compute_profile" in body
    # Every LLM entry should declare its role and where it is used
    for m in body["llms"]:
        assert {"role", "model", "provider", "used_for"}.issubset(m.keys())


def test_forecast_long_term_route(db_available):
    if not db_available:
        pytest.skip("PostgreSQL not reachable — route queries price history from DB")
    r = client.get("/api/forecast/long-term/AAPL")
    assert r.status_code == 200
    body = r.json()
    if "error" in body:
        pytest.skip(f"upstream: {body['error']}")
    assert "forecasts" in body and {"30d", "90d", "180d"}.issubset(body["forecasts"].keys())


def test_forecast_day_trade_route():
    r = client.get("/api/forecast/day-trade/AAPL")
    assert r.status_code == 200
    body = r.json()
    # Could be degraded under rate-limit but must have a known shape
    assert "symbol" in body
    if "error" in body:
        pytest.skip(f"upstream: {body['error']}")
    assert "direction" in body
