"""Nexus API — the single entry point for "say it once, it lands everywhere".

POST /api/nexus/ingest         text or transcript → decomposed actions → applied/proposed
GET  /api/nexus/events         history with undo state
POST /api/nexus/events/{id}/confirm|reject|undo
POST /api/nexus/receipt        receipt text/OCR → pantry + finance (+ shopping)
GET  /api/nexus/brief          "Good morning" digest across all modules
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, get_session
from app.middleware.subscription_gate import check_rate_limit
from app.models.nexus import (
    CalendarEventDB, EmailSignalDB, FastingWindowDB, MedicationDB, MedicationLogDB, NexusEventDB,
    PantryItemDB, ReceiptDB, ReminderDB, ShoppingItemDB, TransactionDB, ChoreDB, ChoreLogDB, FamilyMemberDB,
)
from app.routes.auth import get_current_user
from app.services import nexus_bus
from app.services import intent_engine
from app.services.llm_client import generate_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nexus", tags=["nexus"])


class IngestRequest(BaseModel):
    text: str
    source: str = "text"            # text, voice, telegram
    auto_apply: bool = True         # apply "safe" actions immediately
    use_llm: bool = True
    dry_run: bool = False


class ConfirmRequest(BaseModel):
    action_indexes: Optional[list[int]] = None


class ReceiptText(BaseModel):
    text: str
    store: Optional[str] = None


@router.get("/actions")
async def list_actions():
    return {"actions": nexus_bus.known_actions()}


@router.post("/ingest")
async def ingest(req: IngestRequest, user: UserDB = Depends(check_rate_limit("voice")),
                 db: AsyncSession = Depends(get_session)):
    parsed = await intent_engine.understand(req.text, use_llm=req.use_llm)
    actions = parsed["actions"]

    # resolve member names → ids for calendar/chores/milestones
    if actions:
        res = await db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == user.user_id))
        members = {m.name.lower(): m.id for m in res.scalars().all()}
        for a in actions:
            p = a.get("params", {})
            nm = (p.get("member_name") or "").lower()
            if not nm and a["domain"] in ("calendar", "family", "health"):
                hay = f"{p.get('title', '')} {req.text}".lower()
                nm = next((n for n in members if re.search(rf"\b{re.escape(n)}\b", hay)), "")
                if nm:
                    p["member_name"] = nm.title()
            if nm and nm in members:
                p["member_id"] = members[nm]

    if req.dry_run:
        reply = await intent_engine.spoken_summary(actions, parsed["unparsed"], applied=False)
        return {"actions": actions, "unparsed": parsed["unparsed"], "reply": reply, "event": None}

    if not actions:
        reply = await intent_engine.chat_reply(req.text) if parsed["unparsed"] else "Nothing to do there."
        return {"actions": [], "unparsed": parsed["unparsed"], "reply": reply, "event": None}

    ev = await nexus_bus.emit(db, user.user_id, req.source, "intent.batch",
                              {"intents": actions, "summary": req.text[:140], "raw": req.text[:500]},
                              auto_apply_safe=req.auto_apply)
    applied = ev.status == "applied"
    reply = await intent_engine.spoken_summary(ev.actions or actions, parsed["unparsed"], applied=applied)
    return {"actions": ev.actions, "unparsed": parsed["unparsed"], "reply": reply, "event": nexus_bus.event_to_dict(ev)}


@router.get("/events")
async def events(status: Optional[str] = None, limit: int = 50, user: UserDB = Depends(get_current_user),
                 db: AsyncSession = Depends(get_session)):
    q = select(NexusEventDB).where(NexusEventDB.user_id == user.user_id)
    if status:
        q = q.where(NexusEventDB.status == status)
    q = q.order_by(NexusEventDB.created_at.desc()).limit(min(limit, 200))
    res = await db.execute(q)
    return {"events": [nexus_bus.event_to_dict(e) for e in res.scalars().all()]}


@router.post("/events/{event_id}/confirm")
async def confirm(event_id: str, body: ConfirmRequest = ConfirmRequest(), user: UserDB = Depends(get_current_user),
                  db: AsyncSession = Depends(get_session)):
    try:
        ev = await nexus_bus.confirm(db, user.user_id, event_id, body.action_indexes)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return nexus_bus.event_to_dict(ev)


@router.post("/events/{event_id}/reject")
async def reject(event_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    try:
        ev = await nexus_bus.reject(db, user.user_id, event_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return nexus_bus.event_to_dict(ev)


@router.post("/events/{event_id}/undo")
async def undo(event_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    try:
        ev = await nexus_bus.undo(db, user.user_id, event_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return nexus_bus.event_to_dict(ev)


# ── Receipts ─────────────────────────────────────────────────────────────────
_LINE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9 %&'\-\./]{1,40}?)\s+(?:(?P<qty>\d+(?:\.\d+)?)\s*(?:x|@|lb|lbs|oz|ct)?\s+)?\$?\s?(?P<price>\d{1,4}\.\d{2})\s*[A-Z]?\s*$")
_TOTAL = re.compile(r"\b(?:total|amount due|balance due|grand total)\b[^\d]*(\d{1,5}\.\d{2})", re.I)
_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_SKIP = re.compile(r"\b(subtotal|total|tax|change|cash|visa|master|debit|credit|card|tender|balance|savings|you saved|coupon|thank|store|cashier|register|item count|items sold|approved|auth|ref|terminal|account|xxxx|\*{3,})\b", re.I)
_STORES = ["costco", "walmart", "target", "trader joe", "whole foods", "kroger", "safeway", "aldi", "publix", "h-e-b", "heb", "wegmans", "sprouts", "meijer", "food lion", "harris teeter", "giant", "stop & shop", "shoprite", "winco", "fred meyer", "sam's club", "bj's", "cvs", "walgreens", "amazon", "instacart"]


def parse_receipt_text(text: str, store_hint: Optional[str] = None) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    store = store_hint
    if not store:
        head = " ".join(lines[:6]).lower()
        store = next((s.title() for s in _STORES if s in head), None) or (lines[0][:40] if lines else "Store")
    total = None
    for l in lines:
        m = _TOTAL.search(l)
        if m:
            total = float(m.group(1))
    purchased = None
    for l in lines:
        m = _DATE.search(l)
        if m:
            y = int(m.group(3))
            y = y + 2000 if y < 100 else y
            try:
                purchased = date(y, int(m.group(1)), int(m.group(2)))
                break
            except ValueError:
                pass
    items = []
    for l in lines:
        if _SKIP.search(l):
            continue
        m = _LINE.match(l)
        if not m:
            continue
        name = re.sub(r"\s{2,}", " ", m.group("name")).strip(" -.")
        if len(name) < 3 or name.isdigit():
            continue
        price = float(m.group("price"))
        qty = float(m.group("qty")) if m.group("qty") else 1.0
        items.append({"name": name.title(), "qty": qty, "unit": "count", "price": price,
                      "category": nexus_bus.categorize_item(name)})
    if total is None and items:
        total = round(sum(i["price"] for i in items), 2)
    return {"store": store, "date": (purchased or date.today()).isoformat(), "total": total, "items": items}


async def _llm_receipt(text: str) -> Optional[dict]:
    prompt = f"""Extract this receipt into JSON: {{"store": str, "date": "YYYY-MM-DD", "total": number, "items": [{{"name": str, "qty": number, "unit": str, "price": number, "category": "produce|dairy|meat|seafood|bakery|frozen|pantry|beverage|household"}}]}}
Expand abbreviations to real product names (e.g. "ORG BNLS CHKN BRST" → "Organic Boneless Chicken Breast"). Skip tax/total/payment lines.
Receipt:
{text[:3000]}
Return ONLY JSON."""
    data = await generate_json(prompt, task="fast", timeout=60)
    if isinstance(data, dict) and data.get("items"):
        return data
    return None


async def _process_receipt(db: AsyncSession, user: UserDB, text: str, store_hint: Optional[str]) -> dict:
    parsed = parse_receipt_text(text, store_hint)
    if len(parsed["items"]) < 2:
        llm = await _llm_receipt(text)
        if llm:
            parsed = {**parsed, **{k: v for k, v in llm.items() if v}}
    raw_hash = hashlib.sha256(text.encode()).hexdigest()
    dup = await db.execute(select(ReceiptDB).where(ReceiptDB.user_id == user.user_id, ReceiptDB.raw_hash == raw_hash))
    if dup.scalars().first():
        raise HTTPException(409, "This receipt was already processed.")
    rec = ReceiptDB(user_id=user.user_id, store=parsed.get("store"), total=parsed.get("total"),
                    purchased_on=date.fromisoformat(parsed["date"]) if parsed.get("date") else date.today(),
                    items=parsed["items"], raw_hash=raw_hash,
                    category="grocery" if any(i.get("category") != "household" for i in parsed["items"]) else "household")
    db.add(rec)
    await db.flush()
    payload = {**parsed, "receipt_id": rec.id, "category": rec.category}
    ev = await nexus_bus.emit(db, user.user_id, "receipt", "receipt.parsed", payload)
    rec.nexus_event_id = ev.id
    await db.commit()
    meals = await _meal_ideas(db, user.user_id)
    return {"receipt": {"id": rec.id, **parsed}, "event": nexus_bus.event_to_dict(ev), "meal_ideas": meals}


@router.post("/receipt")
async def receipt_text(body: ReceiptText, user: UserDB = Depends(check_rate_limit("receipt")),
                       db: AsyncSession = Depends(get_session)):
    return await _process_receipt(db, user, body.text, body.store)


@router.post("/receipt/upload")
async def receipt_upload(file: UploadFile = File(...), store: Optional[str] = None,
                         user: UserDB = Depends(check_rate_limit("receipt")), db: AsyncSession = Depends(get_session)):
    data = await file.read()
    text = ""
    if (file.content_type or "").startswith("text/"):
        text = data.decode("utf-8", "ignore")
    else:
        try:
            from app.services.document_ocr import extract_text_from_bytes  # type: ignore
            text = await extract_text_from_bytes(data, file.filename or "receipt")
        except Exception:
            try:
                import io
                import pytesseract
                from PIL import Image
                text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
            except Exception as e:
                raise HTTPException(400, f"Could not OCR receipt: {e}")
    if not text.strip():
        raise HTTPException(400, "No text found in receipt")
    return await _process_receipt(db, user, text, store)


async def _meal_ideas(db: AsyncSession, user_id: str) -> list[dict]:
    res = await db.execute(select(PantryItemDB).where(PantryItemDB.user_id == user_id, PantryItemDB.status == "in_stock"))
    items = res.scalars().all()
    if not items:
        return []
    names = sorted({i.normalized for i in items})
    expiring = sorted([i for i in items if i.expires_on], key=lambda i: i.expires_on)[:5]
    prompt = f"""Pantry: {', '.join(names[:60])}
Use-soon: {', '.join(i.name for i in expiring)}
Suggest 3 quick family dinners (≤35 min) that mostly use the pantry, prioritising use-soon items.
Return ONLY JSON: [{{"title": str, "uses": [str], "missing": [str], "minutes": int}}]"""
    data = await generate_json(prompt, task="fast", timeout=45)
    return data if isinstance(data, list) else []


@router.get("/meal-ideas")
async def meal_ideas(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return {"ideas": await _meal_ideas(db, user.user_id)}


# ── Morning brief ────────────────────────────────────────────────────────────
@router.get("/brief")
async def brief(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    uid = user.user_id
    now = datetime.now()
    today = now.date()
    end = now + timedelta(days=1)

    ev = await db.execute(select(CalendarEventDB).where(CalendarEventDB.user_id == uid, CalendarEventDB.starts_at >= now - timedelta(hours=1),
                                                        CalendarEventDB.starts_at <= end).order_by(CalendarEventDB.starts_at))
    rem = await db.execute(select(ReminderDB).where(ReminderDB.user_id == uid, ReminderDB.status == "pending",
                                                    ReminderDB.due_at <= end).order_by(ReminderDB.due_at))
    meds = await db.execute(select(MedicationDB).where(MedicationDB.user_id == uid, MedicationDB.is_active == True))
    meds = meds.scalars().all()
    taken_today = await db.execute(select(MedicationLogDB.medication_id).where(MedicationLogDB.user_id == uid, MedicationLogDB.taken == True,
                                                                               MedicationLogDB.scheduled_for >= datetime.combine(today, datetime.min.time())))
    taken_ids = {r[0] for r in taken_today.all()}
    fast = await db.execute(select(FastingWindowDB).where(FastingWindowDB.user_id == uid, FastingWindowDB.is_active == True))
    fast = fast.scalars().first()
    sig = await db.execute(select(EmailSignalDB).where(EmailSignalDB.user_id == uid, EmailSignalDB.status == "open",
                                                       EmailSignalDB.category.in_(["bill", "appointment", "school", "action", "renewal"]))
                           .order_by(EmailSignalDB.priority.desc(), EmailSignalDB.due_date.asc().nullslast()).limit(6))
    exp = await db.execute(select(PantryItemDB).where(PantryItemDB.user_id == uid, PantryItemDB.status == "in_stock",
                                                      PantryItemDB.expires_on != None, PantryItemDB.expires_on <= today + timedelta(days=2)))
    shop = await db.execute(select(func.count()).select_from(ShoppingItemDB).where(ShoppingItemDB.user_id == uid, ShoppingItemDB.checked == False))
    pending = await db.execute(select(func.count()).select_from(NexusEventDB).where(NexusEventDB.user_id == uid, NexusEventDB.status == "proposed"))
    spend = await db.execute(select(func.coalesce(func.sum(TransactionDB.amount), 0)).where(TransactionDB.user_id == uid, TransactionDB.occurred_on >= today.replace(day=1)))
    chores = await db.execute(select(ChoreDB, FamilyMemberDB.name).join(FamilyMemberDB, FamilyMemberDB.id == ChoreDB.member_id, isouter=True)
                              .where(ChoreDB.user_id == uid, ChoreDB.is_active == True))
    chores = chores.all()
    done = await db.execute(select(ChoreLogDB.chore_id).where(ChoreLogDB.user_id == uid, ChoreLogDB.day == today))
    done_ids = {r[0] for r in done.all()}

    def _fast_state():
        if not fast:
            return None
        hhmm = now.strftime("%H:%M")
        eating = fast.eating_start <= hhmm < fast.eating_end
        return {"protocol": fast.protocol, "state": "eating window" if eating else "fasting",
                "next_change": fast.eating_end if eating else fast.eating_start}

    data = {
        "date": today.isoformat(),
        "greeting": _greeting(now.hour, user.username),
        "events": [{"id": e.id, "title": e.title, "at": e.starts_at.isoformat(), "location": e.location, "kind": e.kind} for e in ev.scalars().all()],
        "reminders": [{"id": r.id, "title": r.title, "at": r.due_at.isoformat(), "kind": r.kind} for r in rem.scalars().all()],
        "medications": [{"id": m.id, "name": m.name, "dose": m.dose, "times": m.times, "taken_today": m.id in taken_ids} for m in meds],
        "fasting": _fast_state(),
        "radar": [{"id": s.id, "category": s.category, "subject": s.subject, "amount": s.amount,
                   "due_date": s.due_date.isoformat() if s.due_date else None, "priority": s.priority, "deep_link": s.deep_link} for s in sig.scalars().all()],
        "expiring": [{"id": p.id, "name": p.name, "expires_on": p.expires_on.isoformat()} for p in exp.scalars().all()],
        "shopping_open": shop.scalar() or 0,
        "pending_confirmations": pending.scalar() or 0,
        "month_spend": round(float(spend.scalar() or 0), 2),
        "chores": [{"id": c.id, "title": c.title, "who": who, "done": c.id in done_ids} for c, who in chores],
    }
    data["spoken"] = _spoken_brief(data)
    return data


def _greeting(hour: int, name: str) -> str:
    part = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
    return f"{part}, {name.split('@')[0].title()}."


def _spoken_brief(d: dict) -> str:
    bits = [d["greeting"]]
    if d["events"]:
        first = d["events"][0]
        t = datetime.fromisoformat(first["at"]).strftime("%-I:%M %p").lower()
        bits.append(f"You have {len(d['events'])} thing{'s' if len(d['events']) != 1 else ''} on the calendar, starting with {first['title']} at {t}.")
    else:
        bits.append("Calendar's clear today.")
    pend_meds = [m["name"] for m in d["medications"] if not m["taken_today"]]
    if pend_meds:
        bits.append("Meds still due: " + ", ".join(pend_meds) + ".")
    if d["fasting"]:
        bits.append(f"You're in your {d['fasting']['state']} until {d['fasting']['next_change']}.")
    hi = [s for s in d["radar"] if s["priority"] == "high"]
    if hi:
        s = hi[0]
        bits.append(f"Inbox: {len(hi)} urgent — {s['category']} “{s['subject']}”" + (f" due {s['due_date']}" if s["due_date"] else "") + ".")
    if d["expiring"]:
        bits.append("Use soon: " + ", ".join(p["name"] for p in d["expiring"][:3]) + ".")
    if d["pending_confirmations"]:
        bits.append(f"{d['pending_confirmations']} action{'s' if d['pending_confirmations'] != 1 else ''} waiting for your OK.")
    return " ".join(bits)
