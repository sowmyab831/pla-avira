"""Auth-gate middleware + assistant session ownership tests.

The middleware itself is exercised on a small FastAPI app that mounts the
same function — no DB or lifespan needed.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import actor_context_middleware
from app.routes.auth import create_access_token
from app.router_assistant import router as assistant_router


@pytest.fixture
def gate_app():
    app = FastAPI()
    app.middleware("http")(actor_context_middleware)

    @app.get("/api/private/thing")
    def priv():
        return {"ok": True}

    @app.get("/api/public/market/ping")
    def pub():
        return {"ok": True}

    @app.post("/api/telegram/webhook")
    def tg():
        return {"ok": True}

    @app.post("/api/billing/webhook/stripe")
    def bill():
        return {"ok": True}

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    return TestClient(app)


def _hdr(uid: str = "user-a", role: str = "user"):
    return {"Authorization": f"Bearer {create_access_token({'sub': uid, 'role': role})}"}


def test_private_route_requires_token(gate_app):
    assert gate_app.get("/api/private/thing").status_code == 401


def test_private_route_rejects_garbage_token(gate_app):
    r = gate_app.get("/api/private/thing", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_private_route_accepts_valid_token(gate_app):
    r = gate_app.get("/api/private/thing", headers=_hdr())
    assert r.status_code == 200 and r.json()["ok"] is True


def test_expired_token_rejected(gate_app):
    from datetime import timedelta
    tok = create_access_token({"sub": "user-a"}, expires_delta=timedelta(seconds=-10))
    r = gate_app.get("/api/private/thing", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_public_prefixes_open(gate_app):
    assert gate_app.get("/api/public/market/ping").status_code == 200
    assert gate_app.post("/api/telegram/webhook", json={}).status_code == 200
    assert gate_app.post("/api/billing/webhook/stripe", json={}).status_code == 200
    assert gate_app.get("/health/live").status_code == 200


def test_options_preflight_passes(gate_app):
    r = gate_app.options("/api/private/thing", headers={
        "Origin": "http://localhost:30001",
        "Access-Control-Request-Method": "GET",
    })
    assert r.status_code != 401


# ── Assistant session ownership (mounted router, identity override) ──────────

def test_assistant_sessions_scoped_to_principal(api_app):
    build, identity, _ = api_app
    client = build(assistant_router)
    from app.services.session_manager import get_session_manager, MessageRole
    sm = get_session_manager()
    sm.get_or_create_session("user-a", "sess-a1").add_message(MessageRole.USER, "hello")

    # Owner sees their session list
    r = client.get("/api/assistant/sessions")
    assert r.status_code == 200
    ids = [s["session_id"] for s in r.json()["sessions"]]
    assert "sess-a1" in ids

    # Other user sees none of user-a's sessions
    identity["id"] = "user-b"
    r = client.get("/api/assistant/sessions")
    assert "sess-a1" not in [s["session_id"] for s in r.json()["sessions"]]

    # Other user cannot pull or delete the session even knowing its id
    assert client.get("/api/assistant/sessions/sess-a1").status_code == 404
    assert client.delete("/api/assistant/sessions/sess-a1").status_code == 404
    # …and cannot forge ownership via the query param
    assert client.get("/api/assistant/sessions?user_id=user-a").status_code == 403

    # Admin may inspect an explicit partition
    identity["id"] = "admin-1"
    r = client.get("/api/assistant/sessions?user_id=user-a")
    assert r.status_code == 200 and "sess-a1" in [s["session_id"] for s in r.json()["sessions"]]
