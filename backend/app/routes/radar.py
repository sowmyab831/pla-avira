"""Life Admin Radar API — IMAP metadata-only inbox scanning with deep links."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, get_session
from app.middleware.subscription_gate import check_rate_limit, tier_limit
from app.models.nexus import EmailAccountDB, EmailSignalDB
from app.routes.auth import get_current_user
from app.services import imap_radar, nexus_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/radar", tags=["radar"])


class AccountCreate(BaseModel):
    email: EmailStr
    app_password: str
    provider: str = "gmail"
    imap_host: Optional[str] = None
    imap_port: int = 993


class SignalUpdate(BaseModel):
    status: str  # open, done, snoozed, dismissed
    snooze_days: int = 3


class DemoSignals(BaseModel):
    """Feed synthetic header metadata (used for tests / demo without an inbox)."""
    emails: list[dict]


def _acct(a: EmailAccountDB) -> dict:
    return {"id": a.id, "email": a.email, "provider": a.provider, "imap_host": a.imap_host, "is_active": a.is_active,
            "last_sync": a.last_sync.isoformat() if a.last_sync else None}


def _sig(s: EmailSignalDB) -> dict:
    return {"id": s.id, "account_id": s.account_id, "category": s.category, "subject": s.subject,
            "sender_name": s.sender_name, "sender_domain": s.sender_domain,
            "received_at": s.received_at.isoformat() if s.received_at else None,
            "amount": s.amount, "due_date": s.due_date.isoformat() if s.due_date else None,
            "priority": s.priority, "deep_link": s.deep_link, "suggested_reply": s.suggested_reply,
            "status": s.status, "nexus_event_id": s.nexus_event_id}


@router.get("/providers")
async def providers():
    return {"providers": imap_radar.PROVIDERS}


@router.get("/accounts")
async def accounts(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(EmailAccountDB).where(EmailAccountDB.user_id == user.user_id))
    return {"accounts": [_acct(a) for a in res.scalars().all()]}


@router.post("/accounts")
async def add_account(body: AccountCreate, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    cnt = await db.execute(select(func.count()).select_from(EmailAccountDB).where(EmailAccountDB.user_id == user.user_id))
    limit = tier_limit(user, "email_accounts")
    if limit != -1 and (cnt.scalar() or 0) >= limit:
        raise HTTPException(403, {"error": f"Your plan allows {limit} inbox(es). Upgrade to connect more.", "upgrade_url": "/subscription"})
    host = body.imap_host or imap_radar.PROVIDERS.get(body.provider, {}).get("host")
    if not host:
        raise HTTPException(400, "imap_host is required for custom providers")
    secret = body.app_password.replace(" ", "").strip()
    if body.provider == "gmail" and not (len(secret) == 16 and secret.isalpha()):
        raise HTTPException(400, "That looks like your regular Google password. Gmail IMAP only accepts a 16-letter App Password: "
                                 "Google Account → Security → 2-Step Verification → App passwords → create one for 'Avira'.")
    ok, msg = await asyncio.to_thread(imap_radar.test_login_sync, host, body.imap_port, str(body.email), secret)
    if not ok:
        raise HTTPException(400, f"IMAP login failed. {imap_radar.PROVIDERS.get(body.provider, {}).get('help', '')}")
    acct = EmailAccountDB(user_id=user.user_id, email=str(body.email), provider=body.provider, imap_host=host,
                          imap_port=body.imap_port, secret_enc=imap_radar.encrypt_secret(secret))
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return _acct(acct)


@router.delete("/accounts/{account_id}")
async def remove_account(account_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    acct = await db.get(EmailAccountDB, account_id)
    if not acct or acct.user_id != user.user_id:
        raise HTTPException(404, "account not found")
    await db.delete(acct)
    await db.commit()
    return {"ok": True}


async def _store_signals(db: AsyncSession, user_id: str, account_id: str, signals: list[dict]) -> list[EmailSignalDB]:
    stored = []
    for s in signals:
        if s["category"] in ("promo",) or (s["category"] == "other" and s.get("is_list")):
            continue
        if s.get("message_id"):
            dup = await db.execute(select(EmailSignalDB).where(EmailSignalDB.user_id == user_id, EmailSignalDB.message_id == s["message_id"]))
            if dup.scalars().first():
                continue
        row = EmailSignalDB(user_id=user_id, account_id=account_id, message_id=s.get("message_id"), uid=s.get("uid"),
                            sender_domain=s.get("sender_domain"), sender_name=s.get("sender_name"), subject=s.get("subject"),
                            received_at=s.get("received_at"), category=s["category"], amount=s.get("amount"),
                            due_date=s.get("due_date"), priority=s.get("priority", "medium"), deep_link=s.get("deep_link"),
                            suggested_reply=s.get("suggested_reply"))
        db.add(row)
        await db.flush()
        if row.category in ("bill", "appointment", "school", "travel", "action", "renewal", "refund"):
            ev = await nexus_bus.emit(db, user_id, "email", "email.signal", {
                "signal_id": row.id, "category": row.category, "subject": row.subject,
                "due_date": row.due_date.isoformat() if row.due_date else None, "time": s.get("time"),
                "amount": row.amount, "deep_link": row.deep_link})
            row.nexus_event_id = ev.id
        stored.append(row)
    await db.commit()
    return stored


@router.post("/sync")
async def sync(days: int = 14, user: UserDB = Depends(check_rate_limit("radar_sync")), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(EmailAccountDB).where(EmailAccountDB.user_id == user.user_id, EmailAccountDB.is_active == True))
    accts = res.scalars().all()
    if not accts:
        raise HTTPException(400, "No inbox connected. Add one with an app password first.")
    report = []
    for a in accts:
        try:
            raw = await imap_radar.fetch_headers(a.imap_host, a.imap_port, a.email, imap_radar.decrypt_secret(a.secret_enc),
                                                 since_days=min(days, 60), last_uid=a.last_uid or 0)
            sigs = imap_radar.build_signals(raw, a.provider, a.email)
            sigs = await imap_radar.llm_refine(sigs)
            stored = await _store_signals(db, user.user_id, a.id, sigs)
            a.last_sync = datetime.utcnow()
            if raw:
                a.last_uid = max(a.last_uid or 0, max(r["uid"] for r in raw))
            await db.commit()
            report.append({"account": a.email, "scanned": len(raw), "new_signals": len(stored)})
        except Exception as e:
            logger.warning(f"Radar sync failed for {a.email}: {e}")
            report.append({"account": a.email, "error": str(e)})
    return {"report": report}


@router.post("/demo")
async def demo(body: DemoSignals, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Ingest header-only metadata directly (no IMAP). Each item: {subject, from, snippet?, date?, message_id?}."""
    raw = []
    for i, e in enumerate(body.emails):
        name, addr = e.get("from_name"), e.get("from", "noreply@example.com")
        raw.append({"uid": 10_000 + i, "message_id": e.get("message_id") or f"<demo-{datetime.utcnow().timestamp()}-{i}@avira>",
                    "sender_name": name or addr.split("@")[0], "sender_domain": addr.split("@")[-1],
                    "subject": e.get("subject", ""), "received_at": datetime.fromisoformat(e["date"]) if e.get("date") else datetime.utcnow(),
                    "snippet": e.get("snippet", ""), "is_list": False})
    sigs = imap_radar.build_signals(raw, "gmail", user.email or "me")
    stored = await _store_signals(db, user.user_id, "demo", sigs)
    return {"signals": [_sig(s) for s in stored], "classified": [{k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in s.items() if k != "snippet"} for s in sigs]}


@router.get("/signals")
async def signals(status: str = "open", category: Optional[str] = None, user: UserDB = Depends(get_current_user),
                  db: AsyncSession = Depends(get_session)):
    q = select(EmailSignalDB).where(EmailSignalDB.user_id == user.user_id)
    if status != "all":
        q = q.where(EmailSignalDB.status == status)
    if category:
        q = q.where(EmailSignalDB.category == category)
    q = q.order_by(EmailSignalDB.due_date.asc().nullslast(), EmailSignalDB.received_at.desc()).limit(200)
    res = await db.execute(q)
    rows = res.scalars().all()
    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
    # Recompute deep_link with the latest format, fixing any previously broken links.
    acct_ids = {r.account_id for r in rows}
    acct_map = {}
    if acct_ids:
        acct_res = await db.execute(select(EmailAccountDB).where(EmailAccountDB.id.in_(acct_ids)))
        acct_map = {a.id: a for a in acct_res.scalars().all()}
    out = []
    for r in rows:
        s = _sig(r)
        acct = acct_map.get(r.account_id)
        if acct and r.message_id:
            s["deep_link"] = imap_radar.deep_link(acct.provider, r.message_id, acct.email)
        out.append(s)
    return {"signals": out, "counts": by_cat}


@router.patch("/signals/{signal_id}")
async def update_signal(signal_id: str, body: SignalUpdate, user: UserDB = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    s = await db.get(EmailSignalDB, signal_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(404, "signal not found")
    if body.status not in ("open", "done", "snoozed", "dismissed"):
        raise HTTPException(400, "bad status")
    s.status = body.status
    if body.status == "snoozed":
        s.due_date = date.today() + timedelta(days=body.snooze_days)
    await db.commit()
    return _sig(s)
