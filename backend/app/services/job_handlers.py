"""Job handlers — registered kinds for the durable queue.

Import this module at startup (main.py does) so handlers are in the registry
before the scheduler starts calling run_due().
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select, update

from app.database import async_session_maker, PriceSnapshotDB
from app.models.nexus import ReminderDB
from app.models.ops import TrackedProductDB
from app.services.job_queue import handle
from app.services.notification_service import queue_notification

logger = logging.getLogger(__name__)


@handle("reminder.dispatch")
async def reminder_dispatch(payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """Deliver a due reminder: mark sent + queue user-approved notification."""
    reminder_id = payload.get("reminder_id")
    if not reminder_id:
        raise ValueError("payload.reminder_id required")
    async with async_session_maker() as session:
        row = await session.execute(
            select(ReminderDB).where(ReminderDB.id == reminder_id)
        )
        rem = row.scalar_one_or_none()
        if rem is None:
            return {"skipped": "reminder not found"}
        if rem.status not in ("pending",):
            return {"skipped": f"status={rem.status}"}
        rem.status = "sent"
        await session.commit()
        queued = queue_notification(
            rem.user_id, rem.kind or "general",
            rem.title,
            f"Reminder: {rem.title} is due",
        )
        return {"reminder_id": reminder_id, "notification": queued["approval_id"]}


@handle("price.check")
async def price_check(payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """Re-price tracked products; queue an alert when target/drop thresholds hit.

    payload.user_id limits the sweep; omitted checks every active row.
    price_minor in payload lets tests/jobs inject a price without scraping.
    """
    user_id = payload.get("user_id")
    injected_minor: Optional[int] = payload.get("price_minor")
    async with async_session_maker() as session:
        q = select(TrackedProductDB).where(TrackedProductDB.active.is_(True))
        if user_id:
            q = q.where(TrackedProductDB.user_id == user_id)
        tracked = (await session.execute(q)).scalars().all()

        alerts = 0
        checked = 0
        for item in tracked:
            if injected_minor is not None:
                latest_minor = injected_minor
            else:
                snap = await session.execute(
                    select(PriceSnapshotDB.price, PriceSnapshotDB.currency)
                    .where(PriceSnapshotDB.product_key == item.product_key)
                    .order_by(PriceSnapshotDB.captured_at.desc())
                    .limit(1)
                )
                row = snap.first()
                if row is None:
                    continue
                latest_minor = int(round(float(row[0]) * 100))
            checked += 1
            prev_minor = item.last_minor
            item.last_minor = latest_minor

            hit_target = item.target_minor is not None and latest_minor <= item.target_minor
            hit_drop = (
                item.baseline_minor is not None
                and item.baseline_minor > 0
                and (item.baseline_minor - latest_minor) * 100 >= item.drop_pct * item.baseline_minor
            )
            if not (hit_target or hit_drop):
                continue
            # Alert at most once per observed price level.
            if item.last_alerted_at is not None and prev_minor == latest_minor:
                continue
            reason = f"hit your target" if hit_target else f"dropped {item.drop_pct}%+"
            queued = queue_notification(
                item.user_id, "shopping",
                f"Price alert: {item.title}",
                f"{item.title} {reason} — now {item.currency} {latest_minor/100:.2f}",
            )
            item.last_alerted_at = datetime.utcnow()
            alerts += 1
            logger.info(f"price alert for {item.product_key}: {queued['approval_id']}")
        await session.commit()
        return {"checked": checked, "alerts": alerts}
