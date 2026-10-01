"""Nexus: the cross-module event bus.

Flow:
    emit(user, source, event_type, payload)
        → rules produce a list of *proposed* actions
        → if every action is `safe`, they are applied immediately (auto_applied)
        → otherwise the event sits in `proposed` until the user confirms
    confirm(event_id) → applies actions, records result ids
    undo(event_id)    → reverts every applied action via the domain registry

Actions are plain dicts so they serialize to JSON:
    {"domain": "pantry", "action": "add_items", "params": {...},
     "safe": true, "status": "pending|applied|undone|failed", "result": {...}}
"""
from __future__ import annotations

import copy
import logging
import re
from datetime import date, datetime, timedelta, time as dtime
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.nexus import (
    BiometricDB, CalendarEventDB, CheckInDB, ChoreDB, FamilyMemberDB, MedicationDB,
    MedicationLogDB, MilestoneDB, NexusEventDB, PantryItemDB, ReminderDB, ShoppingItemDB,
    TransactionDB, FastingLogDB,
)
from app.models.task import Task

logger = logging.getLogger(__name__)

Handler = Callable[[AsyncSession, str, dict], Awaitable[dict]]
Reverter = Callable[[AsyncSession, str, dict], Awaitable[None]]

_APPLY: dict[str, Handler] = {}
_REVERT: dict[str, Reverter] = {}


def action(domain: str, name: str):
    """Register an apply handler. Handler returns a result dict (must include ids to undo)."""
    def deco(fn: Handler):
        _APPLY[f"{domain}.{name}"] = fn
        return fn
    return deco


def reverter(domain: str, name: str):
    def deco(fn: Reverter):
        _REVERT[f"{domain}.{name}"] = fn
        return fn
    return deco


# ── helpers ──────────────────────────────────────────────────────────────────
PERISHABLE_DAYS = {
    "produce": 7, "dairy": 10, "meat": 3, "seafood": 2, "bakery": 4,
    "frozen": 120, "pantry": 365, "household": 9999, "beverage": 60,
}

_CATEGORY_HINTS = [
    ("produce", r"apple|banana|spinach|lettuce|tomato|onion|pepper|avocado|berr|grape|orange|lemon|lime|carrot|broccoli|potato|cucumber|kale|mango|cilantro|garlic|ginger"),
    ("dairy", r"milk|yogurt|yoghurt|cheese|butter|cream|egg"),
    ("meat", r"chicken|beef|pork|turkey|lamb|steak|ground|sausage|bacon"),
    ("seafood", r"salmon|shrimp|tuna|fish|cod|tilapia"),
    ("bakery", r"bread|bagel|tortilla|bun|muffin|croissant"),
    ("frozen", r"frozen|ice cream|pizza"),
    ("beverage", r"juice|soda|water|coffee|tea|kombucha"),
    ("household", r"paper towel|toilet|detergent|soap|shampoo|diaper|wipes|trash bag|sponge|toothpaste"),
]


def categorize_item(name: str) -> str:
    n = name.lower()
    for cat, pat in _CATEGORY_HINTS:
        if re.search(pat, n):
            return cat
    return "pantry"


def normalize_name(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    n = re.sub(r"\b(organic|fresh|large|small|lb|oz|pack|ct|each|bag|bunch)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, dtime(9, 0))
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except Exception:
        return None


def _parse_date(value: Any) -> Optional[date]:
    dt = _parse_dt(value)
    return dt.date() if dt else None


# ── Domain handlers ──────────────────────────────────────────────────────────
@action("pantry", "add_items")
async def _pantry_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    ids = []
    purchased = _parse_date(p.get("purchased_on")) or date.today()
    for it in p.get("items", []):
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        cat = it.get("category") or categorize_item(name)
        shelf = it.get("perishable_days") or PERISHABLE_DAYS.get(cat, 365)
        row = PantryItemDB(
            user_id=user_id, name=name, normalized=normalize_name(name),
            quantity=float(it.get("qty") or it.get("quantity") or 1), unit=it.get("unit") or "count",
            category=cat, purchased_on=purchased,
            expires_on=purchased + timedelta(days=int(shelf)) if shelf < 9999 else None,
            receipt_id=p.get("receipt_id"),
        )
        db.add(row)
        await db.flush()
        ids.append(row.id)
    return {"ids": ids, "count": len(ids)}


@reverter("pantry", "add_items")
async def _pantry_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    if r.get("ids"):
        await db.execute(delete(PantryItemDB).where(PantryItemDB.id.in_(r["ids"]), PantryItemDB.user_id == user_id))


@action("pantry", "consume")
async def _pantry_consume(db: AsyncSession, user_id: str, p: dict) -> dict:
    changed = []
    for name in p.get("items", []):
        norm = normalize_name(str(name))
        res = await db.execute(select(PantryItemDB).where(
            PantryItemDB.user_id == user_id, PantryItemDB.status == "in_stock",
            PantryItemDB.normalized.like(f"%{norm}%")))
        row = res.scalars().first()
        if row:
            changed.append({"id": row.id, "prev": row.status})
            row.status = "used"
    return {"changed": changed}


@reverter("pantry", "consume")
async def _pantry_consume_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    for c in r.get("changed", []):
        row = await db.get(PantryItemDB, c["id"])
        if row:
            row.status = c["prev"]


@action("finance", "add_transaction")
async def _fin_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    row = TransactionDB(
        user_id=user_id, occurred_on=_parse_date(p.get("date")) or date.today(),
        merchant=p.get("merchant"), amount=float(p.get("amount", 0)),
        category=p.get("category") or "other", source=p.get("source") or "nexus",
        source_id=p.get("source_id"), note=p.get("note"),
    )
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("finance", "add_transaction")
async def _fin_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(TransactionDB).where(TransactionDB.id == r["id"], TransactionDB.user_id == user_id))


def _profile_txns(user_id: str, p: dict) -> list[dict]:
    """Transactions for a profile partition. Default profile = owner's data
    (the 'default' partition plus anything stamped with their real user_id).
    Member profiles live under user_id 'member_<id>'."""
    from app.routes.finance import transactions_store

    profile = p.get("profile") or "default"
    allowed = {profile} if profile != "default" else {"default", user_id}
    return [t for t in transactions_store
            if (t.get("amount") or 0) > 0 and t.get("user_id", "default") in allowed]


@action("finance", "list_recurring_transactions")
async def _fin_recurring(db: AsyncSession, user_id: str, p: dict) -> dict:
    """Detect recurring charges/subscriptions from uploaded statement transactions."""
    from app.routes.finance import detect_recurring

    profile = p.get("profile") or "default"
    partition = profile if profile != "default" else "default"
    result = detect_recurring(partition)
    if not result["recurring"]:
        return {"error": "No transactions found. Upload a bank statement first.", "recurring": []}
    return result


@action("finance", "find_transactions")
async def _fin_find(db: AsyncSession, user_id: str, p: dict) -> dict:
    """Search uploaded statement transactions by keyword (merchant, city, category)."""
    query = str(p.get("query") or "").strip().lower()
    txns = _profile_txns(user_id, p)
    if not txns:
        return {"error": "No transactions found. Upload a bank statement first.", "transactions": []}

    if query:
        matches = [t for t in txns
                   if query in str(t.get("description", "")).lower()
                   or query in str(t.get("category", "")).lower()]
    else:
        matches = txns

    matches = sorted(matches, key=lambda t: t.get("date", ""), reverse=True)[:50]
    total = round(sum(float(t.get("amount", 0)) for t in matches), 2)
    return {"transactions": matches, "count": len(matches), "total": total, "query": query}


@action("shopping", "add_items")
async def _shop_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    ids = []
    for it in p.get("items", []):
        name = it["name"] if isinstance(it, dict) else str(it)
        q = it.get("quantity") if isinstance(it, dict) else None
        row = ShoppingItemDB(user_id=user_id, name=name,
                             quantity=(str(q) if q is not None else None),
                             reason=p.get("reason") or (it.get("reason") if isinstance(it, dict) else None),
                             store_hint=p.get("store_hint"))
        db.add(row)
        await db.flush()
        ids.append(row.id)
    return {"ids": ids, "count": len(ids)}


@reverter("shopping", "add_items")
async def _shop_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    if r.get("ids"):
        await db.execute(delete(ShoppingItemDB).where(ShoppingItemDB.id.in_(r["ids"])))


@action("calendar", "add_event")
async def _cal_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    starts = _parse_dt(p.get("starts_at")) or _parse_dt(p.get("date"))
    if not starts:
        raise ValueError("calendar.add_event requires starts_at")
    try:
        dur = int(p.get("duration_min") or 60)
    except (TypeError, ValueError):
        dur = 60
    dur = dur if 15 <= dur <= 24 * 60 else 60
    ends = _parse_dt(p.get("ends_at")) or (starts + timedelta(minutes=dur))
    row = CalendarEventDB(user_id=user_id, member_id=p.get("member_id"), title=p["title"],
                          starts_at=starts, ends_at=ends, location=p.get("location"),
                          kind=p.get("kind") or "event", source=p.get("source") or "nexus",
                          source_id=p.get("source_id"), notes=p.get("notes"))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("calendar", "add_event")
async def _cal_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(CalendarEventDB).where(CalendarEventDB.id == r["id"]))


@action("reminder", "add")
async def _rem_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    due = _parse_dt(p.get("due_at"))
    if not due:
        raise ValueError("reminder.add requires due_at")
    row = ReminderDB(user_id=user_id, title=p["title"], due_at=due, channel=p.get("channel") or "app",
                     kind=p.get("kind") or "general", source_id=p.get("source_id"))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("reminder", "add")
async def _rem_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(ReminderDB).where(ReminderDB.id == r["id"]))


@action("tasks", "add")
async def _task_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    row = Task(user_id=user_id, title=p["title"], description=p.get("description"),
               category=p.get("category") or "task", due_date=_parse_dt(p.get("due_date")))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("tasks", "add")
async def _task_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(Task).where(Task.id == r["id"]))


@action("health", "add_medication")
async def _med_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    row = MedicationDB(user_id=user_id, member_id=p.get("member_id"), name=p["name"], dose=p.get("dose"),
                       times=p.get("times") or ["08:00"], with_food=p.get("with_food"), notes=p.get("notes"),
                       start_date=_parse_date(p.get("start_date")) or date.today(),
                       end_date=_parse_date(p.get("end_date")), refill_date=_parse_date(p.get("refill_date")))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("health", "add_medication")
async def _med_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(MedicationLogDB).where(MedicationLogDB.medication_id == r["id"]))
    await db.execute(delete(MedicationDB).where(MedicationDB.id == r["id"]))


@action("health", "log_medication")
async def _med_log(db: AsyncSession, user_id: str, p: dict) -> dict:
    name = normalize_name(p.get("name", ""))
    res = await db.execute(select(MedicationDB).where(MedicationDB.user_id == user_id, MedicationDB.is_active == True))
    med = next((m for m in res.scalars().all() if name and name in normalize_name(m.name)), None)
    if not med:
        raise ValueError(f"No active medication matching '{p.get('name')}'")
    row = MedicationLogDB(user_id=user_id, medication_id=med.id, scheduled_for=datetime.utcnow(),
                          taken=bool(p.get("taken", True)), answered_at=datetime.utcnow(), source=p.get("source") or "nexus")
    db.add(row)
    await db.flush()
    return {"id": row.id, "medication": med.name}


@reverter("health", "log_medication")
async def _med_log_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(MedicationLogDB).where(MedicationLogDB.id == r["id"]))


@action("health", "log_biometric")
async def _bio_log(db: AsyncSession, user_id: str, p: dict) -> dict:
    row = BiometricDB(user_id=user_id, member_id=p.get("member_id"), metric=p["metric"], value=float(p["value"]),
                      unit=p.get("unit"), recorded_at=_parse_dt(p.get("recorded_at")) or datetime.utcnow(),
                      source=p.get("source") or "nexus")
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("health", "log_biometric")
async def _bio_log_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(BiometricDB).where(BiometricDB.id == r["id"]))


@action("health", "checkin")
async def _checkin(db: AsyncSession, user_id: str, p: dict) -> dict:
    row = CheckInDB(user_id=user_id, day=_parse_date(p.get("day")) or date.today(), kind=p["kind"], value=str(p.get("value", "yes")))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("health", "checkin")
async def _checkin_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(CheckInDB).where(CheckInDB.id == r["id"]))


@action("health", "log_fasting")
async def _fast_log(db: AsyncSession, user_id: str, p: dict) -> dict:
    row = FastingLogDB(user_id=user_id, day=_parse_date(p.get("day")) or date.today(), kept=bool(p.get("kept", True)),
                       note=p.get("note"), answered_at=datetime.utcnow())
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("health", "log_fasting")
async def _fast_log_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(FastingLogDB).where(FastingLogDB.id == r["id"]))


@action("family", "add_chore")
async def _chore_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    member_id = p.get("member_id")
    if not member_id and p.get("member_name"):
        res = await db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == user_id))
        m = next((x for x in res.scalars().all() if x.name.lower() == str(p["member_name"]).lower()), None)
        member_id = m.id if m else None
    row = ChoreDB(user_id=user_id, member_id=member_id, title=p["title"], recurrence=p.get("recurrence") or "daily",
                  points=int(p.get("points", 1)), due_time=p.get("due_time"))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("family", "add_chore")
async def _chore_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(ChoreDB).where(ChoreDB.id == r["id"]))


@action("family", "add_milestone")
async def _ms_add(db: AsyncSession, user_id: str, p: dict) -> dict:
    member_id = p.get("member_id")
    if not member_id and p.get("member_name"):
        res = await db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == user_id))
        m = next((x for x in res.scalars().all() if x.name.lower() == str(p["member_name"]).lower()), None)
        member_id = m.id if m else None
    row = MilestoneDB(user_id=user_id, member_id=member_id, title=p["title"], category=p.get("category") or "general",
                      achieved_on=_parse_date(p.get("achieved_on")) or date.today(), notes=p.get("notes"))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@reverter("family", "add_milestone")
async def _ms_add_rev(db: AsyncSession, user_id: str, r: dict) -> None:
    await db.execute(delete(MilestoneDB).where(MilestoneDB.id == r["id"]))


@action("health", "analyze")
async def _health_analyze(db: AsyncSession, user_id: str, p: dict) -> dict:
    """Analyze the latest uploaded health/lab report."""
    from app.routes.health import health_reports_store
    from app.services.health_analyzer import get_health_analyzer
    from app.config import settings

    user_reports = [r for r in health_reports_store if r.get("user_id") == user_id]
    if not user_reports:
        return {"error": "No health reports found. Upload a lab report first."}

    report = user_reports[-1]
    cached = report.get("analysis")
    if cached:
        return {"analysis": cached, "source": "cached"}

    lab_results = report.get("lab_results", [])
    alerts = report.get("alerts", [])
    lines = [f"- {r['test_name']}: {r['value']} {r['unit']} (ref: {r['reference_range']}, status: {'abnormal' if r['is_abnormal'] else 'normal'})" for r in lab_results]
    alert_lines = [f"- {a['test_name']}: {a['message']}" for a in alerts]
    report_text = "Lab Results:\n" + "\n".join(lines)
    if alert_lines:
        report_text += "\n\nAlerts:\n" + "\n".join(alert_lines)

    analyzer = get_health_analyzer()
    analysis = await analyzer.analyze_health_report(
        report_text=report_text,
        report_type="blood_test",
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model
    )
    return {"analysis": analysis}


# ── Rules: trigger → proposed actions ────────────────────────────────────────
def rules_for(event_type: str, payload: dict) -> tuple[str, list[dict]]:
    """Return (summary, actions) for a trigger. Pure function → easy to unit test."""
    acts: list[dict] = []

    if event_type == "receipt.parsed":
        items = payload.get("items", [])
        store = payload.get("store") or "store"
        total = payload.get("total")
        grocery_items = [i for i in items if categorize_item(i.get("name", "")) != "household"]
        if grocery_items:
            acts.append(_a("pantry", "add_items", {"items": grocery_items, "purchased_on": payload.get("date"),
                                                   "receipt_id": payload.get("receipt_id")}, safe=True))
        if total:
            acts.append(_a("finance", "add_transaction", {"date": payload.get("date"), "merchant": store, "amount": total,
                                                          "category": payload.get("category") or "grocery",
                                                          "source": "receipt", "source_id": payload.get("receipt_id")}, safe=True))
        summary = f"{store} receipt: {len(items)} items" + (f", ${total:,.2f}" if total else "")
        return summary, acts

    if event_type == "email.signal":
        cat = payload.get("category")
        title = payload.get("subject") or "Email"
        due = payload.get("due_date")
        link = payload.get("deep_link")
        if cat == "bill" and due:
            acts.append(_a("reminder", "add", {"title": f"Pay: {title}", "due_at": f"{due}T09:00:00", "kind": "bill",
                                               "source_id": payload.get("signal_id")}, safe=True))
            acts.append(_a("calendar", "add_event", {"title": f"Bill due: {title}", "starts_at": f"{due}T09:00:00",
                                                     "kind": "bill_due", "source": "email", "notes": link}, safe=True))
        elif cat in ("appointment", "school", "travel") and due:
            acts.append(_a("calendar", "add_event", {"title": title, "starts_at": f"{due}T{payload.get('time') or '09:00'}:00",
                                                     "kind": "appointment" if cat == "appointment" else cat,
                                                     "source": "email", "notes": link}, safe=False))
        elif cat in ("action", "renewal", "refund"):
            acts.append(_a("tasks", "add", {"title": title, "description": link,
                                            "due_date": f"{due}T09:00:00" if due else None}, safe=True))
        return f"Email · {cat}: {title}", acts

    if event_type == "intent.batch":
        # payload = {"intents": [{domain, action, params, safe}]}
        for it in payload.get("intents", []):
            acts.append(_a(it["domain"], it["action"], it.get("params", {}), safe=it.get("safe", False)))
        return payload.get("summary") or f"{len(acts)} actions from voice/text", acts

    if event_type == "pantry.low":
        acts.append(_a("shopping", "add_items", {"items": payload.get("items", []), "reason": "low in pantry"}, safe=True))
        return f"Restock {len(payload.get('items', []))} pantry items", acts

    return payload.get("summary") or event_type, acts


def _a(domain: str, name: str, params: dict, safe: bool = False) -> dict:
    return {"domain": domain, "action": name, "params": params, "safe": safe, "status": "pending", "result": None}


# ── Bus API ──────────────────────────────────────────────────────────────────
def _set_actions(event: NexusEventDB, acts: list[dict]) -> None:
    event.actions = acts
    flag_modified(event, "actions")


async def _apply_actions(db: AsyncSession, user_id: str, event: NexusEventDB) -> None:
    acts = copy.deepcopy(event.actions or [])
    for a in acts:
        if a.get("status") != "pending":
            continue
        key = f"{a['domain']}.{a['action']}"
        fn = _APPLY.get(key)
        if not fn:
            a["status"] = "failed"
            a["error"] = f"unknown action {key}"
            continue
        try:
            a["result"] = await fn(db, user_id, a.get("params") or {})
            a["status"] = "applied"
        except Exception as e:
            a["status"] = "failed"
            a["error"] = str(e)
            logger.warning(f"Nexus action {key} failed: {e}")
    _set_actions(event, acts)
    failed = any(a.get("status") == "failed" for a in acts)
    applied = any(a.get("status") == "applied" for a in acts)
    event.status = ("partially_applied" if applied else "failed") if failed else ("applied" if applied else "rejected")
    event.applied_at = datetime.utcnow() if applied else None


async def emit(db: AsyncSession, user_id: str, source: str, event_type: str, payload: dict,
               auto_apply_safe: bool = True, force_apply: bool = False) -> NexusEventDB:
    summary, acts = rules_for(event_type, payload)
    ev = NexusEventDB(user_id=user_id, source_domain=source, event_type=event_type, summary=summary,
                      payload=payload, actions=acts, status="proposed")
    db.add(ev)
    await db.flush()
    if acts and (force_apply or (auto_apply_safe and all(a.get("safe") for a in acts))):
        await _apply_actions(db, user_id, ev)
        ev.auto_applied = not force_apply
    elif not acts:
        ev.status = "applied"
        ev.applied_at = datetime.utcnow()
    await db.commit()
    await db.refresh(ev)
    return ev


async def confirm(db: AsyncSession, user_id: str, event_id: str, only_indexes: Optional[list[int]] = None) -> NexusEventDB:
    ev = await db.get(NexusEventDB, event_id, with_for_update=True)
    if not ev or ev.user_id != user_id:
        raise ValueError("event not found")
    if ev.status != "proposed":
        return ev
    if only_indexes is not None:
        if any(type(i) is not int or i < 0 or i >= len(ev.actions or []) for i in only_indexes):
            raise ValueError("invalid action index")
        acts = copy.deepcopy(ev.actions or [])
        for i, a in enumerate(acts):
            if i not in only_indexes:
                a["status"] = "skipped"
        _set_actions(ev, acts)
    await _apply_actions(db, user_id, ev)
    await db.commit()
    await db.refresh(ev)
    return ev


async def reject(db: AsyncSession, user_id: str, event_id: str) -> NexusEventDB:
    ev = await db.get(NexusEventDB, event_id, with_for_update=True)
    if not ev or ev.user_id != user_id:
        raise ValueError("event not found")
    if ev.status == "proposed":
        ev.status = "rejected"
        await db.commit()
        await db.refresh(ev)
    return ev


async def undo(db: AsyncSession, user_id: str, event_id: str) -> NexusEventDB:
    ev = await db.get(NexusEventDB, event_id, with_for_update=True)
    if not ev or ev.user_id != user_id:
        raise ValueError("event not found")
    if ev.status not in ("applied", "partially_applied", "partially_undone"):
        return ev
    acts = copy.deepcopy(ev.actions or [])
    for a in reversed(acts):
        if a.get("status") != "applied":
            continue
        fn = _REVERT.get(f"{a['domain']}.{a['action']}")
        if fn and a.get("result"):
            try:
                await fn(db, user_id, a["result"])
                a["status"] = "undone"
            except Exception as e:
                a["error"] = f"undo failed: {e}"
    _set_actions(ev, acts)
    remaining = any(a.get("status") == "applied" for a in acts)
    ev.status = "partially_undone" if remaining else "undone"
    ev.undone_at = None if remaining else datetime.utcnow()
    await db.commit()
    await db.refresh(ev)
    return ev


def event_to_dict(ev: NexusEventDB) -> dict:
    return {
        "id": ev.id, "source": ev.source_domain, "type": ev.event_type, "summary": ev.summary,
        "payload": ev.payload, "actions": ev.actions, "status": ev.status, "auto_applied": ev.auto_applied,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
        "applied_at": ev.applied_at.isoformat() if ev.applied_at else None,
        "undone_at": ev.undone_at.isoformat() if ev.undone_at else None,
    }


def known_actions() -> list[str]:
    return sorted(_APPLY.keys())
