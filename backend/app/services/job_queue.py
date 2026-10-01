"""Durable job queue — Postgres/SQLite backed, survives restarts.

Semantics
- `enqueue()` inserts a pending job; `dedupe_key` makes it idempotent.
- `run_due()` claims due jobs (FOR UPDATE SKIP LOCKED on Postgres, a
  process-level lock on SQLite) and executes registered handlers.
- Crash recovery: `recover_stale()` re-pends claims whose lock expired.
- Retries: failure re-pends with exponential backoff until max_attempts,
  then status='dead'.

Handlers are registered with `@handle("kind")` and must be importable at
startup — see `app/services/job_handlers.py`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy import select, update, func

from app.database import async_session_maker
from app.models.ops import JobDB

logger = logging.getLogger(__name__)

Handler = Callable[[Dict[str, Any], str], Awaitable[Optional[Dict[str, Any]]]]
_HANDLERS: Dict[str, Handler] = {}
_sqlite_lock = asyncio.Lock()
_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
LOCK_TTL_SECONDS = 300


def handle(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[kind] = fn
        return fn
    return deco


def _dialect_is_pg(session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


async def enqueue(
    kind: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    run_at: Optional[datetime] = None,
    dedupe_key: Optional[str] = None,
    max_attempts: int = 3,
) -> str:
    """Persist a job. Returns the job id (existing id if dedupe_key hit)."""
    async with async_session_maker() as session:
        if dedupe_key:
            row = await session.execute(
                select(JobDB.id).where(JobDB.dedupe_key == dedupe_key)
            )
            existing = row.scalar_one_or_none()
            if existing:
                return existing
        job = JobDB(
            kind=kind,
            payload=payload or {},
            run_at=run_at or datetime.utcnow(),
            dedupe_key=dedupe_key,
            max_attempts=max_attempts,
        )
        session.add(job)
        await session.commit()
        return job.id


async def _claim_due(session, limit: int) -> list:
    """Atomically claim up to `limit` due pending jobs for this worker."""
    now = datetime.utcnow()
    if _dialect_is_pg(session):
        rows = await session.execute(
            select(JobDB)
            .where(JobDB.status == "pending", JobDB.run_at <= now)
            .order_by(JobDB.run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = rows.scalars().all()
        for j in jobs:
            j.status = "claimed"
            j.locked_by = _WORKER_ID
            j.locked_at = now
    else:
        async with _sqlite_lock:
            rows = await session.execute(
                select(JobDB)
                .where(JobDB.status == "pending", JobDB.run_at <= now)
                .order_by(JobDB.run_at)
                .limit(limit)
            )
            jobs = rows.scalars().all()
            for j in jobs:
                j.status = "claimed"
                j.locked_by = _WORKER_ID
                j.locked_at = now
    await session.commit()
    return list(jobs)


async def run_due(limit: int = 25) -> Dict[str, int]:
    """Claim and execute due jobs. Returns outcome counts."""
    await recover_stale()
    async with async_session_maker() as session:
        jobs = await _claim_due(session, limit)

    stats = {"claimed": len(jobs), "done": 0, "retry": 0, "dead": 0, "unknown": 0}
    for job in jobs:
        handler = _HANDLERS.get(job.kind)
        if handler is None:
            stats["unknown"] += 1
            await _settle(job.id, status="dead", error=f"no handler registered for kind '{job.kind}'")
            continue
        try:
            result = await handler(job.payload or {}, job.id)
            await _settle(job.id, status="done", result=result)
            stats["done"] += 1
        except Exception as e:
            logger.warning(f"job {job.id} ({job.kind}) attempt {job.attempts + 1} failed: {e}")
            if job.attempts + 1 >= job.max_attempts:
                await _settle(job.id, status="dead", error=str(e)[:2000])
                stats["dead"] += 1
            else:
                backoff = min(3600, 30 * (2 ** job.attempts))
                await _settle(
                    job.id, status="pending",
                    run_at=datetime.utcnow() + timedelta(seconds=backoff),
                    error=str(e)[:2000],
                )
                stats["retry"] += 1
    return stats


async def _settle(job_id: str, *, status: str, result: Any = None,
                  error: Optional[str] = None, run_at: Optional[datetime] = None) -> None:
    async with async_session_maker() as session:
        values: Dict[str, Any] = {
            "status": status,
            "locked_by": None,
            "locked_at": None,
            "last_error": error,
            "attempts": JobDB.attempts + 1,
        }
        if status in ("done", "dead"):
            values["finished_at"] = datetime.utcnow()
        if result is not None:
            values["result"] = result
        if run_at is not None:
            values["run_at"] = run_at
        await session.execute(
            update(JobDB).where(JobDB.id == job_id).values(**values)
        )
        await session.commit()


async def recover_stale(older_than_seconds: int = LOCK_TTL_SECONDS) -> int:
    """Re-pend claims whose lock has expired (worker crashed mid-job)."""
    cutoff = datetime.utcnow() - timedelta(seconds=older_than_seconds)
    async with async_session_maker() as session:
        res = await session.execute(
            update(JobDB)
            .where(JobDB.status == "claimed", JobDB.locked_at < cutoff)
            .values(status="pending", locked_by=None, locked_at=None)
        )
        await session.commit()
        return res.rowcount or 0


async def job_stats() -> Dict[str, int]:
    async with async_session_maker() as session:
        rows = await session.execute(
            select(JobDB.status, func.count()).group_by(JobDB.status)
        )
        return {row[0]: row[1] for row in rows}
