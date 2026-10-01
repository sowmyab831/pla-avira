"""Shared offline test fixtures.

- `sqlite_db`: in-memory SQLite with an async-compatible adapter (real SQL,
  no deployment database).
- `api_app`: FastAPI app factory that injects the SQLite session and lets a test
  switch the authenticated principal via `identity['id']`.
- `postgres` marker: tests that require real PostgreSQL semantics (row locks,
  concurrency). Skipped unless AVIRA_TEST_DATABASE_URL is set.
"""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, UserDB, get_session
from app.routes.auth import get_current_user


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: requires AVIRA_TEST_DATABASE_URL (PostgreSQL)")
    config.addinivalue_line("markers", "live_llm: opt-in test that calls the local Ollama server")


def pytest_collection_modifyitems(config, items):
    pg_skip = pytest.mark.skip(reason="AVIRA_TEST_DATABASE_URL not set")
    llm_skip = pytest.mark.skip(reason="AVIRA_LIVE_LLM_TESTS not set")
    for item in items:
        if "postgres" in item.keywords and not os.getenv("AVIRA_TEST_DATABASE_URL"):
            item.add_marker(pg_skip)
        if "live_llm" in item.keywords and not os.getenv("AVIRA_LIVE_LLM_TESTS"):
            item.add_marker(llm_skip)


class AsyncSessionAdapter:
    """Run a sync SQLAlchemy Session behind the async interface routes expect."""

    def __init__(self, session: Session):
        self.session = session

    async def execute(self, query, *a, **kw):
        return self.session.execute(query, *a, **kw)

    async def get(self, model, key):
        return self.session.get(model, key)

    def add(self, row):
        self.session.add(row)

    def add_all(self, rows):
        self.session.add_all(rows)

    async def delete(self, row):
        self.session.delete(row)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, row):
        self.session.refresh(row)

    def begin_nested(self):
        return self.session.begin_nested()

    def get_bind(self):
        return self.session.get_bind()


class _AsyncSessionCtx:
    """`async with fake_session_maker() as s` adapter over the sync session."""

    def __init__(self, session: Session):
        self._adapter = AsyncSessionAdapter(session)

    async def __aenter__(self):
        return self._adapter

    async def __aexit__(self, *exc):
        if exc[0] is not None:
            self._adapter.session.rollback()
        return False


@pytest.fixture
def fake_session_maker(sqlite_db):
    """Callable matching `async_session_maker()` — returns an async ctx manager
    over the shared sqlite_db session. Tests monkeypatch it into services that
    open their own sessions (job_queue, memory, job_handlers)."""
    def _make():
        return _AsyncSessionCtx(sqlite_db)
    return _make


@pytest.fixture
def sqlite_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    yield session
    session.close()
    engine.dispose()


def make_user(session: Session, user_id: str, role: str = "user") -> UserDB:
    user = UserDB(user_id=user_id, username=user_id, email=f"{user_id}@example.test",
                  password_hash="test-only", role=role, subscription_tier="free")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def api_app(sqlite_db):
    """Yield (client, identity, session). Tests set identity['id'] to switch principal."""
    identity = {"id": "user-a"}
    for uid in ("user-a", "user-b"):
        make_user(sqlite_db, uid)
    make_user(sqlite_db, "admin-1", role="admin")
    adapter = AsyncSessionAdapter(sqlite_db)

    def build(*routers) -> TestClient:
        app = FastAPI()
        for r in routers:
            app.include_router(r)
        app.dependency_overrides[get_current_user] = lambda: sqlite_db.get(UserDB, identity["id"])
        app.dependency_overrides[get_session] = lambda: adapter
        return TestClient(app)

    yield build, identity, sqlite_db
