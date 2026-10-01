"""Family Hub — members vault, chores, calendar, reminders, milestones, and
one-tap generators (babysitter sheet, packing list, kids worksheet)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, get_session
from app.middleware.subscription_gate import tier_limit
from app.models.nexus import (CalendarEventDB, ChoreDB, ChoreLogDB, FamilyMemberDB, MedicationDB, MilestoneDB, ReminderDB)
from app.routes.auth import get_current_user
from app.services.llm_client import generate_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/family-hub", tags=["family-hub"])


class MemberIn(BaseModel):
    name: str
    role: str = "child"
    birthdate: Optional[date] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    sizes: Optional[dict] = None
    allergies: Optional[list[str]] = None
    wishlist: Optional[list[dict]] = None
    interests: Optional[list[str]] = None
    emergency: Optional[dict] = None
    notes: Optional[str] = None


class ChoreIn(BaseModel):
    title: str
    member_id: Optional[str] = None
    recurrence: str = "daily"
    points: int = 1
    due_time: Optional[str] = None


class EventIn(BaseModel):
    title: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    member_id: Optional[str] = None
    location: Optional[str] = None
    kind: str = "event"
    notes: Optional[str] = None


class ReminderIn(BaseModel):
    title: str
    due_at: datetime
    kind: str = "general"
    channel: str = "app"


class MilestoneIn(BaseModel):
    title: str
    member_id: Optional[str] = None
    category: str = "general"
    achieved_on: Optional[date] = None
    notes: Optional[str] = None


def _age(b: Optional[date]) -> Optional[int]:
    if not b:
        return None
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def _m(m: FamilyMemberDB) -> dict:
    return {"id": m.id, "name": m.name, "role": m.role, "birthdate": m.birthdate.isoformat() if m.birthdate else None,
            "age": _age(m.birthdate), "school": m.school, "grade": m.grade, "sizes": m.sizes or {}, "allergies": m.allergies or [],
            "wishlist": m.wishlist or [], "interests": m.interests or [], "emergency": m.emergency or {}, "notes": m.notes,
            "status": getattr(m, "status", "active") or "active"}


# Lifecycle: invited → active → removed. DELETE soft-removes (keeps history
# attributable); ?hard=true permanently deletes.
_MEMBER_TRANSITIONS = {"invited": {"active", "removed"}, "active": {"removed"}, "removed": set()}


# ── Members ──────────────────────────────────────────────────────────────────
@router.get("/members")
async def members(include_removed: bool = False, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    q = select(FamilyMemberDB).where(FamilyMemberDB.user_id == user.user_id).order_by(FamilyMemberDB.created_at)
    if not include_removed:
        q = q.where(FamilyMemberDB.status != "removed")
    res = await db.execute(q)
    out = [_m(m) for m in res.scalars().all()]
    upcoming = []
    for m in out:
        if m["birthdate"]:
            b = date.fromisoformat(m["birthdate"])
            nxt = b.replace(year=date.today().year)
            if nxt < date.today():
                nxt = nxt.replace(year=date.today().year + 1)
            upcoming.append({"name": m["name"], "on": nxt.isoformat(), "in_days": (nxt - date.today()).days, "turning": (m["age"] or 0) + 1})
    return {"members": out, "birthdays": sorted(upcoming, key=lambda x: x["in_days"])}


@router.post("/members")
async def add_member(body: MemberIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    cnt = await db.execute(select(func.count()).select_from(FamilyMemberDB).where(FamilyMemberDB.user_id == user.user_id))
    lim = tier_limit(user, "family_members")
    if lim != -1 and (cnt.scalar() or 0) >= lim:
        raise HTTPException(403, {"error": f"Your plan allows {lim} family members.", "upgrade_url": "/subscription"})
    m = FamilyMemberDB(user_id=user.user_id, **body.model_dump(exclude_none=True))
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return _m(m)


@router.patch("/members/{member_id}")
async def update_member(member_id: str, body: dict, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = await db.get(FamilyMemberDB, member_id)
    if not m or m.user_id != user.user_id:
        raise HTTPException(404, "member not found")
    for k in ("name", "role", "school", "grade", "sizes", "allergies", "wishlist", "interests", "emergency", "notes"):
        if k in body:
            setattr(m, k, body[k])
    if "birthdate" in body:
        m.birthdate = date.fromisoformat(body["birthdate"]) if body["birthdate"] else None
    if "status" in body:
        cur = getattr(m, "status", "active") or "active"
        nxt = body["status"]
        if nxt != cur and nxt not in _MEMBER_TRANSITIONS.get(cur, set()):
            raise HTTPException(409, f"invalid status transition {cur} → {nxt}")
        m.status = nxt
    await db.commit()
    return _m(m)


@router.delete("/members/{member_id}")
async def delete_member(member_id: str, hard: bool = False, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = await db.get(FamilyMemberDB, member_id)
    if not m or m.user_id != user.user_id:
        raise HTTPException(404, "member not found")
    if hard:
        await db.delete(m)
    else:
        m.status = "removed"
    await db.commit()
    return {"ok": True, "status": "deleted" if hard else "removed"}


def member_profile_id(member_id: str) -> str:
    """Data partition key for a family member's health/finance records."""
    return f"member_{member_id}"


@router.get("/oversight")
async def family_oversight(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Head-of-family view: per-member health & finance wellbeing.

    Enterprise plan feature — each member's uploads are stored under the
    partition user_id 'member_<id>' (own directory in document storage).
    """
    tier = getattr(user, "subscription_tier", "free") or "free"
    if tier != "enterprise" and getattr(user, "role", "") != "admin":
        raise HTTPException(403, {"error": "Family oversight requires the Enterprise plan.",
                                  "current_tier": tier, "upgrade_url": "/subscription"})

    from app.routes.finance import finance_reports_store
    from app.routes.health import health_reports_store

    res = await db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == user.user_id).order_by(FamilyMemberDB.created_at))
    out = []
    for m in res.scalars().all():
        uid = member_profile_id(m.id)

        fin = [r for r in finance_reports_store if r.get("user_id") == uid]
        fin_txns = [t for r in fin for t in r.get("transactions", []) if (t.get("amount") or 0) > 0]
        cats: dict[str, float] = {}
        for t in fin_txns:
            c = t.get("category") or "Other"
            cats[c] = cats.get(c, 0) + float(t.get("amount", 0))

        hlth = [r for r in health_reports_store if r.get("user_id") == uid]
        alerts = [a for r in hlth for a in (r.get("alerts") or [])]
        abnormal = [lr for r in hlth for lr in (r.get("lab_results") or []) if lr.get("is_abnormal")]

        out.append({
            "id": m.id, "name": m.name, "role": m.role, "age": _age(m.birthdate),
            "profile_user_id": uid,
            "finance": {
                "reports": len(fin),
                "total_spent": round(sum(float(t.get("amount", 0)) for t in fin_txns), 2),
                "transaction_count": len(fin_txns),
                "top_categories": dict(sorted(cats.items(), key=lambda x: -x[1])[:5]),
                "last_upload": max((r.get("uploaded_at") for r in fin), default=None),
            },
            "health": {
                "reports": len(hlth),
                "alerts": len(alerts),
                "abnormal_results": len(abnormal),
                "alert_messages": [str(a.get("message", a)) if isinstance(a, dict) else str(a) for a in alerts[:5]],
                "last_report": max((r.get("report_date") or r.get("uploaded_at") for r in hlth), default=None),
            },
        })
    return {"members": out, "count": len(out)}


# ── Chores ───────────────────────────────────────────────────────────────────
def _due_today(rec: str, today: date) -> bool:
    if rec == "daily":
        return True
    if rec == "weekdays":
        return today.weekday() < 5
    if rec.startswith("weekly"):
        parts = rec.split(":")
        if len(parts) == 2:
            return today.strftime("%a").lower()[:3] == parts[1][:3].lower()
        return True
    return rec == "once"


@router.get("/chores")
async def chores(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    today = date.today()
    res = await db.execute(select(ChoreDB, FamilyMemberDB.name).join(FamilyMemberDB, FamilyMemberDB.id == ChoreDB.member_id, isouter=True)
                           .where(ChoreDB.user_id == user.user_id, ChoreDB.is_active == True))
    rows = res.all()
    logs = await db.execute(select(ChoreLogDB).where(ChoreLogDB.user_id == user.user_id, ChoreLogDB.day >= today - timedelta(days=7)))
    logs = logs.scalars().all()
    done_today = {l.chore_id for l in logs if l.day == today}
    points: dict[str, int] = {}
    for c, who in rows:
        wk = sum(1 for l in logs if l.chore_id == c.id)
        points[who or "Family"] = points.get(who or "Family", 0) + wk * c.points
    return {"chores": [{"id": c.id, "title": c.title, "who": who, "member_id": c.member_id, "recurrence": c.recurrence, "points": c.points,
                        "due_time": c.due_time, "due_today": _due_today(c.recurrence, today), "done_today": c.id in done_today} for c, who in rows],
            "weekly_points": points}


@router.post("/chores")
async def add_chore(body: ChoreIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    c = ChoreDB(user_id=user.user_id, **body.model_dump())
    db.add(c)
    await db.commit()
    return {"id": c.id}


@router.post("/chores/{chore_id}/done")
async def chore_done(chore_id: str, undo: bool = False, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    c = await db.get(ChoreDB, chore_id)
    if not c or c.user_id != user.user_id:
        raise HTTPException(404, "chore not found")
    if undo:
        await db.execute(delete(ChoreLogDB).where(ChoreLogDB.chore_id == chore_id, ChoreLogDB.day == date.today()))
    else:
        db.add(ChoreLogDB(user_id=user.user_id, chore_id=chore_id, day=date.today()))
        if c.recurrence == "once":
            c.is_active = False
    await db.commit()
    return {"ok": True}


@router.delete("/chores/{chore_id}")
async def delete_chore(chore_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    c = await db.get(ChoreDB, chore_id)
    if not c or c.user_id != user.user_id:
        raise HTTPException(404, "chore not found")
    c.is_active = False
    await db.commit()
    return {"ok": True}


# ── Calendar + reminders ─────────────────────────────────────────────────────
@router.get("/calendar")
async def calendar(days: int = 14, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    start = datetime.combine(date.today(), datetime.min.time())
    res = await db.execute(select(CalendarEventDB, FamilyMemberDB.name).join(FamilyMemberDB, FamilyMemberDB.id == CalendarEventDB.member_id, isouter=True)
                           .where(CalendarEventDB.user_id == user.user_id, CalendarEventDB.starts_at >= start,
                                  CalendarEventDB.starts_at <= start + timedelta(days=days)).order_by(CalendarEventDB.starts_at))
    return {"events": [{"id": e.id, "title": e.title, "starts_at": e.starts_at.isoformat(), "ends_at": e.ends_at.isoformat() if e.ends_at else None,
                        "who": who, "member_id": e.member_id, "location": e.location, "kind": e.kind, "source": e.source, "notes": e.notes}
                       for e, who in res.all()]}


@router.post("/calendar")
async def add_event(body: EventIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    e = CalendarEventDB(user_id=user.user_id, source="manual", **body.model_dump())
    db.add(e)
    await db.commit()
    return {"id": e.id}


@router.delete("/calendar/{event_id}")
async def delete_event(event_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await db.execute(delete(CalendarEventDB).where(CalendarEventDB.id == event_id, CalendarEventDB.user_id == user.user_id))
    await db.commit()
    return {"ok": True}


@router.get("/reminders")
async def reminders(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(ReminderDB).where(ReminderDB.user_id == user.user_id, ReminderDB.status.in_(["pending", "sent"]))
                           .order_by(ReminderDB.due_at).limit(100))
    return {"reminders": [{"id": r.id, "title": r.title, "due_at": r.due_at.isoformat(), "kind": r.kind, "status": r.status} for r in res.scalars().all()]}


@router.post("/reminders")
async def add_reminder(body: ReminderIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    r = ReminderDB(user_id=user.user_id, **body.model_dump())
    db.add(r)
    await db.commit()
    return {"id": r.id}


@router.patch("/reminders/{rem_id}")
async def update_reminder(rem_id: str, body: dict, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    r = await db.get(ReminderDB, rem_id)
    if not r or r.user_id != user.user_id:
        raise HTTPException(404, "reminder not found")
    if "status" in body:
        r.status = body["status"]
    if "due_at" in body:
        r.due_at = datetime.fromisoformat(body["due_at"])
    await db.commit()
    return {"ok": True}


# ── Milestones ───────────────────────────────────────────────────────────────
@router.get("/milestones")
async def milestones(member_id: Optional[str] = None, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    q = select(MilestoneDB, FamilyMemberDB.name).join(FamilyMemberDB, FamilyMemberDB.id == MilestoneDB.member_id, isouter=True).where(MilestoneDB.user_id == user.user_id)
    if member_id:
        q = q.where(MilestoneDB.member_id == member_id)
    res = await db.execute(q.order_by(MilestoneDB.achieved_on.desc()))
    return {"milestones": [{"id": m.id, "title": m.title, "who": who, "category": m.category,
                            "achieved_on": m.achieved_on.isoformat() if m.achieved_on else None, "notes": m.notes} for m, who in res.all()]}


@router.post("/milestones")
async def add_milestone(body: MilestoneIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = MilestoneDB(user_id=user.user_id, **body.model_dump(exclude_none=True))
    if not m.achieved_on:
        m.achieved_on = date.today()
    db.add(m)
    await db.commit()
    return {"id": m.id}


# ── Generators ───────────────────────────────────────────────────────────────
@router.get("/babysitter-sheet")
async def babysitter_sheet(hours: int = 6, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Everything a sitter needs tonight, assembled from the vault — no typing."""
    res = await db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == user.user_id))
    ms = res.scalars().all()
    kids = [m for m in ms if m.role == "child"]
    now = datetime.now()
    ev = await db.execute(select(CalendarEventDB).where(CalendarEventDB.user_id == user.user_id, CalendarEventDB.starts_at >= now,
                                                        CalendarEventDB.starts_at <= now + timedelta(hours=hours)).order_by(CalendarEventDB.starts_at))
    meds = await db.execute(select(MedicationDB).where(MedicationDB.user_id == user.user_id, MedicationDB.is_active == True, MedicationDB.member_id != None))
    meds = meds.scalars().all()
    sheet = {
        "generated_at": now.isoformat(),
        "kids": [{"name": k.name, "age": _age(k.birthdate), "allergies": k.allergies or [], "notes": k.notes,
                  "meds_tonight": [{"name": m.name, "dose": m.dose, "times": [t for t in (m.times or []) if t >= now.strftime("%H:%M")]}
                                   for m in meds if m.member_id == k.id],
                  "likes": (k.interests or [])[:5]} for k in kids],
        "emergency": [{"for": m.name, **(m.emergency or {})} for m in ms if m.emergency],
        "schedule": [{"at": e.starts_at.strftime("%-I:%M %p"), "what": e.title, "where": e.location} for e in ev.scalars().all()],
        "house_rules": ["Screens off 30 min before bed", "No nuts in the house" if any("nut" in a.lower() for k in kids for a in (k.allergies or [])) else "Snacks are in the pantry, top shelf"],
    }
    lines = [f"Babysitter sheet — {now.strftime('%a %b %-d, %-I:%M %p')}", ""]
    for k in sheet["kids"]:
        lines.append(f"{k['name']} ({k['age']}yo)" + (f" — ALLERGIES: {', '.join(k['allergies'])}" if k["allergies"] else ""))
        for m in k["meds_tonight"]:
            if m["times"]:
                lines.append(f"  • {m['name']} {m['dose'] or ''} at {', '.join(m['times'])}")
        if k["likes"]:
            lines.append(f"  • Likes: {', '.join(k['likes'])}")
    if sheet["schedule"]:
        lines += ["", "Tonight:"] + [f"  {s['at']} — {s['what']}" + (f" @ {s['where']}" if s["where"] else "") for s in sheet["schedule"]]
    if sheet["emergency"]:
        lines += ["", "Emergency:"] + [f"  {e['for']}: " + ", ".join(f"{k} {v}" for k, v in e.items() if k != "for") for e in sheet["emergency"]]
    lines += ["", "House rules:"] + [f"  • {r}" for r in sheet["house_rules"]]
    sheet["text"] = "\n".join(lines)
    return sheet


class PackingIn(BaseModel):
    destination: str
    nights: int = 3
    climate: str = "mild"           # hot, cold, mild, rainy
    member_ids: Optional[list[str]] = None
    activities: list[str] = []


@router.post("/packing-list")
async def packing_list(body: PackingIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(FamilyMemberDB).where(FamilyMemberDB.user_id == user.user_id))
    ms = [m for m in res.scalars().all() if not body.member_ids or m.id in body.member_ids]
    meds = await db.execute(select(MedicationDB).where(MedicationDB.user_id == user.user_id, MedicationDB.is_active == True))
    meds = meds.scalars().all()
    base = ["Phone chargers", "Toiletries bag", "Reusable water bottles", "Snacks for the road", "Documents / IDs", "First-aid mini kit"]
    climate = {"hot": ["Sunscreen SPF50", "Hats", "Swimsuits", "Sandals"], "cold": ["Warm jackets", "Gloves", "Beanies", "Thermal layers"],
               "rainy": ["Rain jackets", "Umbrella", "Waterproof shoes"], "mild": ["Light jacket", "Comfortable walking shoes"]}.get(body.climate, [])
    per_person = []
    for m in ms:
        n = body.nights
        items = [f"{n + 1} outfits", f"{n + 1} underwear/socks", "Pyjamas"]
        age = _age(m.birthdate)
        if age is not None and age <= 3:
            items += ["Diapers/wipes", "Favourite comfort toy", "Sippy cup"]
        elif age is not None and age <= 10:
            items += ["Activity book / tablet + headphones", "Favourite stuffed animal"]
        for md in meds:
            if md.member_id == m.id or (md.member_id is None and m.role in ("parent", "partner")):
                items.append(f"{md.name} ({n + 1} days)")
        if m.sizes and m.role == "child":
            items.append(f"(sizes: {', '.join(f'{k} {v}' for k, v in m.sizes.items())})")
        per_person.append({"name": m.name, "items": items})
    acts = []
    for a in body.activities:
        al = a.lower()
        if "beach" in al or "pool" in al or "swim" in al:
            acts += ["Towels", "Goggles", "Swim diapers" if any((_age(m.birthdate) or 99) <= 3 for m in ms) else "Beach toys"]
        if "hik" in al:
            acts += ["Hiking shoes", "Daypack", "Bug spray"]
        if "ski" in al or "snow" in al:
            acts += ["Ski gloves", "Goggles", "Hand warmers"]
        if "wedding" in al or "formal" in al:
            acts += ["Formal outfit", "Dress shoes"]
    return {"destination": body.destination, "nights": body.nights, "shared": base + climate + sorted(set(acts)), "per_person": per_person}


class WorksheetIn(BaseModel):
    member_id: Optional[str] = None
    subject: str = "math"       # math, reading, spelling, science
    minutes: int = 10
    theme: Optional[str] = None


@router.post("/worksheet")
async def worksheet(body: WorksheetIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    age, name, interests, grade = 7, "your child", [], None
    if body.member_id:
        m = await db.get(FamilyMemberDB, body.member_id)
        if m and m.user_id == user.user_id:
            age, name, interests, grade = _age(m.birthdate) or 7, m.name, m.interests or [], m.grade
    theme = body.theme or (interests[0] if interests else "animals")
    prompt = f"""Create a {body.minutes}-minute {body.subject} practice sheet for {name}, age {age}{f', grade {grade}' if grade else ''}. Theme: {theme}.
Age-appropriate, fun, 6-8 questions, with an answer key. Return ONLY JSON:
{{"title": str, "instructions": str, "questions": [{{"q": str, "answer": str}}], "bonus": str}}"""
    data = await generate_json(prompt, task="fast", timeout=60)
    if not isinstance(data, dict) or not data.get("questions"):
        data = {"title": f"{theme.title()} {body.subject} practice", "instructions": "Answer each question. Ask a grown-up if stuck!",
                "questions": [{"q": f"If you see {i + 2} {theme} and {i + 1} more arrive, how many are there?", "answer": str(2 * i + 3)} for i in range(6)],
                "bonus": f"Draw your favourite {theme}."}
    return {"for": name, "age": age, **data}
