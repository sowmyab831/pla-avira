"""Release 0: settings ownership and legacy-auth removal regressions."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import user_settings


def test_unauthenticated_settings_access_fails(sqlite_db):
    app = FastAPI()
    app.include_router(user_settings.router)
    client = TestClient(app)
    assert client.get("/api/settings/features/user-a").status_code in (401, 403)
    assert client.put("/api/settings/features/user-a", json={}).status_code in (401, 403)


def test_user_cannot_read_or_write_other_user_settings(api_app):
    build, identity, _ = api_app
    client = build(user_settings.router)

    identity["id"] = "user-a"
    r = client.put("/api/settings/features/user-a", json={"theme": "light", "show_travel": False})
    assert r.status_code == 200, r.text

    identity["id"] = "user-b"
    assert client.get("/api/settings/features/user-a").status_code == 403
    assert client.put("/api/settings/features/user-a", json={"theme": "dark"}).status_code == 403
    assert client.post("/api/settings/features/user-a/toggle?feature=show_travel&enabled=true").status_code == 403
    assert client.get("/api/settings/features/user-a/sync").status_code == 403

    identity["id"] = "user-a"
    data = client.get("/api/settings/features/user-a").json()["settings"]
    assert data["theme"] == "light" and data["show_travel"] is False


def test_me_alias_and_admin_read_only(api_app):
    build, identity, _ = api_app
    client = build(user_settings.router)

    identity["id"] = "user-a"
    assert client.put("/api/settings/features/me", json={"default_currency": "INR"}).status_code == 200
    assert client.get("/api/settings/features/me").json()["settings"]["default_currency"] == "INR"

    identity["id"] = "admin-1"
    assert client.get("/api/settings/features/user-a").status_code == 200
    assert client.put("/api/settings/features/user-a", json={"default_currency": "USD"}).status_code == 403


def test_toggle_rejects_unknown_feature(api_app):
    build, identity, _ = api_app
    client = build(user_settings.router)
    assert client.post("/api/settings/features/me/toggle?feature=is_admin&enabled=true").status_code == 400


def test_legacy_local_auth_endpoints_removed():
    from app.main import app
    paths = {r.path for r in app.routes}
    assert not any(p.startswith("/api/local-auth") for p in paths), paths
    import importlib
    import pytest
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.services.auth_service")
