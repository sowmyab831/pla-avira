"""Releases 2–5 regression tests: memory/capture, durable jobs, family member
lifecycle, tracked products + price alerts, org policy, telemetry."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.database import PriceSnapshotDB
from app.models.nexus import FamilyMemberDB, ReminderDB
from app.models.ops import JobDB, MemoryItemDB, TrackedProductDB
from app.routes.memory import router as memory_router
from app.routes.shopping import router as shopping_router
from app.routes.family_hub import router as family_hub_router
from app.routes.ai_settings import router as ai_router
from app.services import job_queue, memory as mem_svc, job_handlers  # noqa: F401 (registers handlers)
from app.services.notification_service import get_pending_notifications


@pytest.fixture
def wired(sqlite_db, fake_session_maker, monkeypatch):
    """Point service-level session factories at the test SQLite session."""
    monkeypatch.setattr(job_queue, "async_session_maker", fake_session_maker)
    monkeypatch.setattr(mem_svc, "async_session_maker", fake_session_maker)
    monkeypatch.setattr(job_handlers, "async_session_maker", fake_session_maker)
    return sqlite_db


# ── R2: memory + capture ─────────────────────────────────────────────────────

def test_memory_crud_and_scoping(api_app, wired):
    build, identity, _ = api_app
    client = build(memory_router)

    r = client.post("/api/memory", json={"text": "Ava's school pickup is at 3pm", "kind": "fact", "tags": ["school"]})
    assert r.status_code == 200 and r.json()["item"]["kind"] == "fact"
    mid = r.json()["item"]["id"]

    r = client.get("/api/memory")
    assert [m["id"] for m in r.json()["items"]] == [mid]

    r = client.get("/api/memory/search", params={"q": "school pickup"})
    assert r.json()["items"][0]["id"] == mid

    # user-b cannot see or delete user-a's memory
    identity["id"] = "user-b"
    assert client.get("/api/memory").json()["count"] == 0
    assert client.get("/api/memory/search", params={"q": "school"}).json()["count"] == 0
    assert client.delete(f"/api/memory/{mid}").status_code == 404
    assert client.patch(f"/api/memory/{mid}", json={"text": "hijack"}).status_code == 404

    identity["id"] = "user-a"
    assert client.patch(f"/api/memory/{mid}", json={"pinned": True}).json()["item"]["pinned"] is True
    assert client.delete(f"/api/memory/{mid}").status_code == 200
    assert client.get("/api/memory").json()["count"] == 0


def test_capture_and_recall(api_app, wired):
    build, identity, _ = api_app
    client = build(memory_router)

    client.post("/api/capture", json={"text": "Flight to Mumbai lands Dec 12", "tags": ["travel"]})
    client.post("/api/capture", json={"text": "Air fryer target price $80"})
    r = client.get("/api/capture")
    assert r.json()["count"] == 2
    assert all(i["kind"] == "capture" for i in r.json()["items"])

    # recall surfaces token-relevant memory
    import asyncio
    lines = asyncio.run(mem_svc.recall("user-a", "when does the mumbai flight land?"))
    assert lines and "Mumbai" in lines[0]


def test_recall_pinned_first(sqlite_db, wired):
    import asyncio
    async def main():
        await mem_svc.add_memory("u1", "random note about gardening")
        await mem_svc.add_memory("u1", "Peanut allergy — severe", pinned=True, kind="fact")
        lines = await mem_svc.recall("u1", "gardening")
        assert lines[0].startswith("[fact] Peanut")
    asyncio.run(main())


# ── R3: durable job queue ────────────────────────────────────────────────────

def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_job_enqueue_dedupe_and_run(sqlite_db, wired):
    async def main():
        called = []

        @job_queue.handle("test.echo")
        async def _h(payload, job_id):
            called.append(payload)
            return {"echo": payload}

        j1 = await job_queue.enqueue("test.echo", {"n": 1}, dedupe_key="dup-1")
        j2 = await job_queue.enqueue("test.echo", {"n": 2}, dedupe_key="dup-1")
        assert j1 == j2  # idempotent enqueue

        stats = await job_queue.run_due()
        assert stats["done"] == 1 and called == [{"n": 1}]
        job = sqlite_db.get(JobDB, j1)
        assert job.status == "done" and job.result == {"echo": {"n": 1}}
    _run(main())


def test_job_retry_then_dead(sqlite_db, wired):
    async def main():
        @job_queue.handle("test.fail")
        async def _h(payload, job_id):
            raise RuntimeError("boom")

        jid = await job_queue.enqueue("test.fail", {}, max_attempts=2)
        stats = await job_queue.run_due()
        assert stats["retry"] == 1
        job = sqlite_db.get(JobDB, jid)
        assert job.status == "pending" and job.attempts == 1 and job.run_at > datetime.utcnow()

        # force due and run again → dead
        job.run_at = datetime.utcnow() - timedelta(seconds=1)
        sqlite_db.commit()
        stats = await job_queue.run_due()
        assert stats["dead"] == 1
        job = sqlite_db.get(JobDB, jid)
        assert job.status == "dead" and "boom" in job.last_error
    _run(main())


def test_job_crash_recovery(sqlite_db, wired):
    async def main():
        jid = await job_queue.enqueue("test.echo2", {})
        # simulate a worker that claimed then died
        job = sqlite_db.get(JobDB, jid)
        job.status, job.locked_by, job.locked_at = "claimed", "dead-worker", datetime.utcnow() - timedelta(seconds=999)
        sqlite_db.commit()
        recovered = await job_queue.recover_stale()
        assert recovered == 1
        assert sqlite_db.get(JobDB, jid).status == "pending"
    _run(main())


def test_job_unknown_kind_dies(sqlite_db, wired):
    async def main():
        jid = await job_queue.enqueue("no.such.handler", {})
        stats = await job_queue.run_due()
        assert stats["unknown"] == 1
        assert sqlite_db.get(JobDB, jid).status == "dead"
    _run(main())


def test_reminder_dispatch_handler(sqlite_db, wired):
    async def main():
        rem = ReminderDB(user_id="user-a", title="Take medication", due_at=datetime.utcnow(),
                         kind="med", status="pending")
        sqlite_db.add(rem)
        sqlite_db.commit()

        jid = await job_queue.enqueue("reminder.dispatch", {"reminder_id": rem.id})
        stats = await job_queue.run_due()
        assert stats["done"] == 1
        assert sqlite_db.get(ReminderDB, rem.id).status == "sent"
        assert sqlite_db.get(JobDB, jid).result["reminder_id"] == rem.id

        # idempotent: re-running a sent reminder skips
        jid2 = await job_queue.enqueue("reminder.dispatch", {"reminder_id": rem.id})
        await job_queue.run_due()
        assert sqlite_db.get(JobDB, jid2).result["skipped"] == "status=sent"
    _run(main())


# ── R3: family member state machine ─────────────────────────────────────────

def test_family_member_lifecycle(api_app, sqlite_db):
    build, identity, _ = api_app
    client = build(family_hub_router)

    r = client.post("/api/family-hub/members", json={"name": "Kid", "role": "child"})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert r.json()["status"] == "active"

    # invalid transition (active → invited not allowed)
    r = client.patch(f"/api/family-hub/members/{mid}", json={"status": "invited"})
    assert r.status_code == 409

    # soft delete keeps the row but hides it from the default list
    r = client.delete(f"/api/family-hub/members/{mid}")
    assert r.json()["status"] == "removed"
    assert client.get("/api/family-hub/members").json()["members"] == []
    listed = client.get("/api/family-hub/members", params={"include_removed": True}).json()["members"]
    assert listed[0]["status"] == "removed"

    # hard delete actually removes
    r = client.delete(f"/api/family-hub/members/{mid}", params={"hard": True})
    assert r.json()["status"] == "deleted"
    assert client.get("/api/family-hub/members", params={"include_removed": True}).json()["members"] == []


def test_family_member_scoping(api_app, sqlite_db):
    build, identity, _ = api_app
    client = build(family_hub_router)
    sqlite_db.add(FamilyMemberDB(user_id="user-b", name="OtherKid", status="active"))
    sqlite_db.commit()
    other = sqlite_db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == "user-b")).scalar_one()

    identity["id"] = "user-a"  # cannot touch user-b's member
    assert client.patch(f"/api/family-hub/members/{other.id}", json={"status": "removed"}).status_code == 404
    assert client.delete(f"/api/family-hub/members/{other.id}").status_code == 404


# ── R4: tracked products + price alerts ─────────────────────────────────────

def test_tracked_product_routes(api_app, wired, sqlite_db):
    build, identity, _ = api_app
    client = build(shopping_router)

    r = client.post("/api/shopping/tracked", json={
        "title": "Dyson V15 Vacuum", "retailer": "amazon", "target_price": 500.0, "drop_pct": 15})
    assert r.status_code == 200
    item = r.json()["item"]
    assert item["target_price"] == 500.0 and item["retailer"] == "amazon"

    # re-tracking the same product is idempotent
    r2 = client.post("/api/shopping/tracked", json={"title": "Dyson V15 Vacuum", "retailer": "amazon"})
    assert r2.json().get("already_tracked") is True

    assert client.get("/api/shopping/tracked").json()["count"] == 1

    identity["id"] = "user-b"
    assert client.get("/api/shopping/tracked").json()["count"] == 0
    assert client.delete(f"/api/shopping/tracked/{item['id']}").status_code == 404

    identity["id"] = "user-a"
    assert client.delete(f"/api/shopping/tracked/{item['id']}").status_code == 200


def test_price_check_alerts(sqlite_db, wired):
    async def main():
        tp = TrackedProductDB(user_id="user-a", product_key="dyson v15|amazon",
                              title="Dyson V15", retailer="amazon", currency="USD",
                              target_minor=50000, baseline_minor=79900, drop_pct=10)
        sqlite_db.add(tp)
        sqlite_db.commit()

        # price at $450 → both target and >10% drop hit
        jid = await job_queue.enqueue("price.check", {"user_id": "user-a", "price_minor": 45000})
        stats = await job_queue.run_due()
        assert stats["done"] == 1
        res = sqlite_db.get(JobDB, jid).result
        assert res["checked"] == 1 and res["alerts"] == 1
        assert sqlite_db.get(TrackedProductDB, tp.id).last_minor == 45000
        pending = get_pending_notifications("user-a")
        assert any("Dyson V15" in n["title"] for n in pending)

        # same price again → no duplicate alert
        await job_queue.enqueue("price.check", {"user_id": "user-a", "price_minor": 45000})
        await job_queue.run_due()
        assert sqlite_db.get(TrackedProductDB, tp.id).last_minor == 45000
        assert len([n for n in get_pending_notifications("user-a") if "Dyson V15" in n["title"]]) == 1

        # price rises above baseline → no drop, no target hit → no alert
        await job_queue.enqueue("price.check", {"user_id": "user-a", "price_minor": 85000})
        stats = await job_queue.run_due()
        res = sqlite_db.execute(select(JobDB).order_by(JobDB.created_at.desc())).scalars().first().result
        assert res["alerts"] == 0
    _run(main())


def test_price_check_uses_snapshot_history(sqlite_db, wired):
    async def main():
        tp = TrackedProductDB(user_id="user-a", product_key="air fryer|walmart",
                              title="Air Fryer", retailer="walmart", currency="USD",
                              target_minor=8000, baseline_minor=12000, drop_pct=10)
        sqlite_db.add(tp)
        sqlite_db.add(PriceSnapshotDB(product_key="air fryer|walmart", retailer="walmart",
                                    title="Air Fryer", price=75.0, currency="USD"))
        sqlite_db.commit()
        jid = await job_queue.enqueue("price.check", {"user_id": "user-a"})
        await job_queue.run_due()
        res = sqlite_db.get(JobDB, jid).result
        assert res["checked"] == 1 and res["alerts"] == 1
    _run(main())


# ── R5: org policy + telemetry ───────────────────────────────────────────────

def test_org_policy_admin_only(api_app, wired):
    build, identity, _ = api_app
    client = build(ai_router)

    identity["id"] = "user-a"
    assert client.get("/api/ai/admin/org-policy").status_code == 403
    assert client.put("/api/ai/admin/org-policy", json={"cloud_allowed": True}).status_code == 403
    assert client.get("/api/ai/admin/metrics").status_code == 403

    identity["id"] = "admin-1"
    r = client.get("/api/ai/admin/org-policy")
    assert r.status_code == 200 and r.json()["cloud_allowed"] is False

    # cloud flag off → cannot enable org cloud
    r = client.put("/api/ai/admin/org-policy", json={"cloud_allowed": True})
    assert r.status_code == 403

    r = client.put("/api/ai/admin/org-policy",
                   json={"cloud_allowed": False, "allowed_providers": ["ollama"], "monthly_cap_micro_usd": 5000000})
    assert r.status_code == 200
    r = client.get("/api/ai/admin/org-policy")
    assert r.json()["allowed_providers"] == ["ollama"]

    # unknown provider rejected
    assert client.put("/api/ai/admin/org-policy",
                      json={"allowed_providers": ["bogus"]}).status_code == 400

    # metrics endpoint returns telemetry sections
    r = client.get("/api/ai/admin/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "http" in body and "jobs" in body and "ai_usage_events" in body
