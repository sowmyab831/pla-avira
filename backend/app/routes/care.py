"""Care API — medications, fasting, biometrics, 1-tap check-ins, micro-workouts.

Everything here is designed for zero-friction daily use: one tap or one
sentence to Avira. Trends are computed server-side for the dashboard.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, get_session
from app.models.nexus import (BiometricDB, CheckInDB, FastingLogDB, FastingWindowDB, MedicationDB, MedicationLogDB,
                              ReminderDB)
from app.routes.auth import get_current_user
from app.services.llm_client import generate_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/care", tags=["care"])


class MedicationIn(BaseModel):
    name: str
    dose: Optional[str] = None
    times: list[str] = ["08:00"]
    with_food: Optional[str] = None
    notes: Optional[str] = None
    member_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    refill_date: Optional[date] = None


class MedLogIn(BaseModel):
    taken: bool = True
    scheduled_for: Optional[datetime] = None
    source: str = "app"


class FastingIn(BaseModel):
    protocol: str = "16:8"
    eating_start: str = "12:00"
    eating_end: str = "20:00"
    days: list[int] = [0, 1, 2, 3, 4, 5, 6]


class FastLogIn(BaseModel):
    kept: bool = True
    day: Optional[date] = None
    note: Optional[str] = None


class BiometricIn(BaseModel):
    metric: str
    value: float
    unit: Optional[str] = None
    recorded_at: Optional[datetime] = None
    member_id: Optional[str] = None


class CheckInIn(BaseModel):
    kind: str
    value: str = "yes"
    day: Optional[date] = None


def _med(m: MedicationDB, logs_today: set[str]) -> dict:
    return {"id": m.id, "name": m.name, "dose": m.dose, "times": m.times, "with_food": m.with_food, "notes": m.notes,
            "member_id": m.member_id, "is_active": m.is_active, "refill_date": m.refill_date.isoformat() if m.refill_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None, "taken_today": m.id in logs_today}


# ── Medications ──────────────────────────────────────────────────────────────
@router.get("/medications")
async def list_meds(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(MedicationDB).where(MedicationDB.user_id == user.user_id).order_by(MedicationDB.created_at))
    start = datetime.combine(date.today(), datetime.min.time())
    logs = await db.execute(select(MedicationLogDB.medication_id).where(MedicationLogDB.user_id == user.user_id,
                                                                        MedicationLogDB.taken == True, MedicationLogDB.scheduled_for >= start))
    taken = {r[0] for r in logs.all()}
    return {"medications": [_med(m, taken) for m in res.scalars().all()]}


@router.post("/medications")
async def add_med(body: MedicationIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = MedicationDB(user_id=user.user_id, **body.model_dump(exclude_none=True))
    if not m.start_date:
        m.start_date = date.today()
    db.add(m)
    if body.refill_date:
        db.add(ReminderDB(user_id=user.user_id, title=f"Refill {body.name}", kind="refill",
                          due_at=datetime.combine(body.refill_date - timedelta(days=3), datetime.min.time().replace(hour=9))))
    await db.commit()
    await db.refresh(m)
    return _med(m, set())


@router.patch("/medications/{med_id}")
async def update_med(med_id: str, body: dict, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = await db.get(MedicationDB, med_id)
    if not m or m.user_id != user.user_id:
        raise HTTPException(404, "medication not found")
    for k in ("name", "dose", "times", "with_food", "notes", "is_active", "member_id"):
        if k in body:
            setattr(m, k, body[k])
    for k in ("end_date", "refill_date", "start_date"):
        if k in body:
            setattr(m, k, date.fromisoformat(body[k]) if body[k] else None)
    await db.commit()
    return _med(m, set())


@router.delete("/medications/{med_id}")
async def delete_med(med_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = await db.get(MedicationDB, med_id)
    if not m or m.user_id != user.user_id:
        raise HTTPException(404, "medication not found")
    await db.execute(delete(MedicationLogDB).where(MedicationLogDB.medication_id == med_id))
    await db.delete(m)
    await db.commit()
    return {"ok": True}


@router.post("/medications/{med_id}/log")
async def log_med(med_id: str, body: MedLogIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = await db.get(MedicationDB, med_id)
    if not m or m.user_id != user.user_id:
        raise HTTPException(404, "medication not found")
    row = MedicationLogDB(user_id=user.user_id, medication_id=med_id, scheduled_for=body.scheduled_for or datetime.utcnow(),
                          taken=body.taken, answered_at=datetime.utcnow(), source=body.source)
    db.add(row)
    await db.commit()
    return {"id": row.id, "taken": row.taken}


@router.get("/medications/adherence")
async def adherence(days: int = 30, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    since = datetime.utcnow() - timedelta(days=days)
    res = await db.execute(select(MedicationLogDB.medication_id, MedicationLogDB.taken, func.count())
                           .where(MedicationLogDB.user_id == user.user_id, MedicationLogDB.scheduled_for >= since)
                           .group_by(MedicationLogDB.medication_id, MedicationLogDB.taken))
    stats: dict[str, dict] = {}
    for mid, taken, n in res.all():
        s = stats.setdefault(mid, {"taken": 0, "missed": 0})
        s["taken" if taken else "missed"] += n
    meds = await db.execute(select(MedicationDB).where(MedicationDB.user_id == user.user_id))
    out = []
    for m in meds.scalars().all():
        s = stats.get(m.id, {"taken": 0, "missed": 0})
        expected = len(m.times or []) * days
        pct = round(100 * s["taken"] / expected) if expected else None
        out.append({"id": m.id, "name": m.name, **s, "expected": expected, "adherence_pct": pct})
    return {"days": days, "medications": out}


# ── Fasting ──────────────────────────────────────────────────────────────────
@router.get("/fasting")
async def get_fasting(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(FastingWindowDB).where(FastingWindowDB.user_id == user.user_id, FastingWindowDB.is_active == True))
    w = res.scalars().first()
    logs = await db.execute(select(FastingLogDB).where(FastingLogDB.user_id == user.user_id).order_by(FastingLogDB.day.desc()).limit(30))
    logs = logs.scalars().all()
    streak = 0
    d = date.today()
    by_day = {l.day: l.kept for l in logs}
    while by_day.get(d) is True:
        streak += 1
        d -= timedelta(days=1)
    now = datetime.now().strftime("%H:%M")
    state = None
    if w:
        eating = w.eating_start <= now < w.eating_end
        state = {"state": "eating" if eating else "fasting", "next_change": w.eating_end if eating else w.eating_start}
    return {"window": {"id": w.id, "protocol": w.protocol, "eating_start": w.eating_start, "eating_end": w.eating_end, "days": w.days} if w else None,
            "now": state, "streak_days": streak,
            "logs": [{"day": l.day.isoformat(), "kept": l.kept, "note": l.note} for l in logs]}


@router.post("/fasting")
async def set_fasting(body: FastingIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(FastingWindowDB).where(FastingWindowDB.user_id == user.user_id, FastingWindowDB.is_active == True))
    for w in res.scalars().all():
        w.is_active = False
    w = FastingWindowDB(user_id=user.user_id, **body.model_dump())
    db.add(w)
    await db.commit()
    return {"id": w.id, "protocol": w.protocol, "eating_start": w.eating_start, "eating_end": w.eating_end}


@router.post("/fasting/log")
async def log_fast(body: FastLogIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    day = body.day or date.today()
    res = await db.execute(select(FastingLogDB).where(FastingLogDB.user_id == user.user_id, FastingLogDB.day == day))
    row = res.scalars().first()
    if row:
        row.kept, row.note, row.answered_at = body.kept, body.note, datetime.utcnow()
    else:
        row = FastingLogDB(user_id=user.user_id, day=day, kept=body.kept, note=body.note, answered_at=datetime.utcnow())
        db.add(row)
    await db.commit()
    return {"day": day.isoformat(), "kept": body.kept}


# ── Biometrics ───────────────────────────────────────────────────────────────
@router.get("/biometrics")
async def biometrics(metric: Optional[str] = None, days: int = 90, user: UserDB = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    since = datetime.utcnow() - timedelta(days=days)
    q = select(BiometricDB).where(BiometricDB.user_id == user.user_id, BiometricDB.recorded_at >= since)
    if metric:
        q = q.where(BiometricDB.metric == metric)
    res = await db.execute(q.order_by(BiometricDB.recorded_at))
    rows = res.scalars().all()
    series: dict[str, list] = {}
    for r in rows:
        series.setdefault(r.metric, []).append({"t": r.recorded_at.isoformat(), "v": r.value, "unit": r.unit})
    trends = {}
    for k, pts in series.items():
        if len(pts) >= 2:
            first, last = pts[0]["v"], pts[-1]["v"]
            trends[k] = {"first": first, "last": last, "delta": round(last - first, 2), "n": len(pts), "unit": pts[-1]["unit"]}
    return {"series": series, "trends": trends}


@router.post("/biometrics")
async def add_biometric(body: BiometricIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = BiometricDB(user_id=user.user_id, **body.model_dump(exclude_none=True))
    db.add(row)
    await db.commit()
    return {"id": row.id}


# ── Check-ins ────────────────────────────────────────────────────────────────
@router.get("/checkins")
async def checkins(days: int = 14, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    since = date.today() - timedelta(days=days)
    res = await db.execute(select(CheckInDB).where(CheckInDB.user_id == user.user_id, CheckInDB.day >= since).order_by(CheckInDB.day.desc()))
    rows = res.scalars().all()
    today = [r for r in rows if r.day == date.today()]
    streaks = {}
    for kind in ("workout", "water", "stretch", "sleep"):
        s, d = 0, date.today()
        days_done = {r.day for r in rows if r.kind == kind and r.value == "yes"}
        if d not in days_done:
            d -= timedelta(days=1)
        while d in days_done:
            s += 1
            d -= timedelta(days=1)
        streaks[kind] = s
    return {"today": [{"kind": r.kind, "value": r.value} for r in today],
            "history": [{"day": r.day.isoformat(), "kind": r.kind, "value": r.value} for r in rows], "streaks": streaks}


@router.post("/checkins")
async def add_checkin(body: CheckInIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    day = body.day or date.today()
    res = await db.execute(select(CheckInDB).where(CheckInDB.user_id == user.user_id, CheckInDB.day == day, CheckInDB.kind == body.kind))
    row = res.scalars().first()
    if row:
        row.value, row.answered_at = body.value, datetime.utcnow()
    else:
        row = CheckInDB(user_id=user.user_id, day=day, kind=body.kind, value=body.value)
        db.add(row)
    await db.commit()
    return {"id": row.id, "kind": row.kind, "value": row.value}


# ── Micro-workouts & due-now card ────────────────────────────────────────────
_MICRO = [
    {"title": "Desk reset", "minutes": 3, "moves": ["20 chair squats", "10 desk push-ups", "30s neck rolls"]},
    {"title": "Kettle break", "minutes": 4, "moves": ["15 calf raises", "20 standing marches", "10 wall angels", "30s calf stretch"]},
    {"title": "Core snack", "minutes": 5, "moves": ["30s plank", "15 dead bugs", "20 glute bridges", "repeat x2"]},
    {"title": "Stairs sprint", "minutes": 5, "moves": ["5 rounds: up briskly, down slow", "30s rest between"]},
    {"title": "Mobility minute", "minutes": 2, "moves": ["10 cat-cows", "10 hip circles each side", "30s deep squat hold"]},
    {"title": "Parking-lot power", "minutes": 4, "moves": ["20 walking lunges", "10 incline push-ups on bumper", "20 jumping jacks"]},
]


@router.get("/micro-workout")
async def micro_workout(minutes: int = 5, user: UserDB = Depends(get_current_user)):
    opts = [m for m in _MICRO if m["minutes"] <= max(minutes, 2)] or _MICRO[:1]
    return {"workout": opts[datetime.now().day % len(opts)], "alternatives": opts}


@router.get("/due-now")
async def due_now(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """What needs a yes/no right now: meds in the last/next hour, fasting question after window, check-ins not answered."""
    now = datetime.now()
    hhmm = now.strftime("%H:%M")
    start = datetime.combine(now.date(), datetime.min.time())
    meds = await db.execute(select(MedicationDB).where(MedicationDB.user_id == user.user_id, MedicationDB.is_active == True))
    logs = await db.execute(select(MedicationLogDB).where(MedicationLogDB.user_id == user.user_id, MedicationLogDB.scheduled_for >= start))
    answered = {(l.medication_id, l.scheduled_for.strftime("%H") if l.scheduled_for else "") for l in logs.scalars().all()}
    prompts = []
    for m in meds.scalars().all():
        for t in m.times or []:
            try:
                th = int(t[:2])
            except ValueError:
                continue
            if th <= now.hour and (m.id, f"{th:02d}") not in answered and any((m.id, f"{h:02d}") not in answered for h in [th]):
                already = any(k[0] == m.id and k[1] and abs(int(k[1]) - th) <= 1 for k in answered)
                if not already:
                    prompts.append({"type": "med", "id": m.id, "title": f"Did you take {m.name}{(' ' + m.dose) if m.dose else ''}?", "scheduled": t})
    fast = await db.execute(select(FastingWindowDB).where(FastingWindowDB.user_id == user.user_id, FastingWindowDB.is_active == True))
    w = fast.scalars().first()
    if w and hhmm >= w.eating_end:
        fl = await db.execute(select(FastingLogDB).where(FastingLogDB.user_id == user.user_id, FastingLogDB.day == now.date()))
        if not fl.scalars().first():
            prompts.append({"type": "fasting", "title": f"Did you keep your {w.protocol} fast today?"})
    ci = await db.execute(select(CheckInDB.kind).where(CheckInDB.user_id == user.user_id, CheckInDB.day == now.date()))
    done = {r[0] for r in ci.all()}
    if now.hour >= 17 and "workout" not in done:
        prompts.append({"type": "checkin", "kind": "workout", "title": "Did you move today? Even 5 minutes counts."})
    if now.hour >= 20 and "mood" not in done:
        prompts.append({"type": "checkin", "kind": "mood", "title": "How was today, one word?"})
    return {"prompts": prompts}


@router.get("/insights")
async def insights(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """LLM-written, plain-English weekly health nudge from local data only."""
    bio = await biometrics(None, 30, user, db)
    adh = await adherence(14, user, db)
    fast = await get_fasting(user, db)
    ci = await checkins(14, user, db)
    prompt = f"""You are Avira, a caring, concise British health companion (not a doctor). Using ONLY this data, write 3 short bullet insights and 1 suggested tiny habit for the coming week. No medical diagnoses.
Biometric trends: {bio['trends']}
Medication adherence (14d): {[{k: v for k, v in m.items() if k in ('name','adherence_pct','missed')} for m in adh['medications']]}
Fasting streak: {fast['streak_days']} days; protocol: {fast['window']['protocol'] if fast['window'] else 'none'}
Check-in streaks: {ci['streaks']}
Return ONLY JSON: {{"insights": [str, str, str], "habit": str}}"""
    data = await generate_json(prompt, task="fast", timeout=45)
    if not isinstance(data, dict):
        data = {"insights": ["Log a weight and one workout this week to unlock trends."], "habit": "Two-minute stretch after brushing your teeth."}
    return data
