"""
Maintenance Hub — research-backed home/vehicle/appliance checklists.

Templates follow standard industry guidance (InterNACHI standards of practice,
HUD healthy-homes guidance, manufacturer service intervals). All checklist
logic is deterministic; AI is only used for the explicit opt-in
"research this repair" endpoint.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    get_session, MaintenanceItemDB, ApplianceDB, RepairLogDB, UserDB,
)
from app.routes.auth import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# ── Research-based checklist templates (deterministic) ────────────────────

HOME_TEMPLATES = [
    # Monthly
    {"id": "hvac_filter", "task": "Replace HVAC filter", "season": "monthly", "interval_months": 2,
     "why": "Dirty filters cut efficiency 5-15% and strain the blower motor."},
    {"id": "range_hood", "task": "Clean range hood filter", "season": "monthly", "interval_months": 3,
     "why": "Grease buildup is a fire risk and reduces ventilation."},
    # Spring
    {"id": "gutters_spring", "task": "Clean gutters & downspouts", "season": "spring", "interval_months": 6,
     "why": "Clogged gutters cause roof/foundation water damage — the #1 preventable repair."},
    {"id": "roof_inspect", "task": "Inspect roof (shingles, flashing)", "season": "spring", "interval_months": 12,
     "why": "Catching a lifted shingle early avoids a $5k+ deck replacement."},
    {"id": "ac_service", "task": "Service AC before summer", "season": "spring", "interval_months": 12,
     "why": "Annual service maintains efficiency and warranty coverage."},
    {"id": "smoke_detectors_spring", "task": "Test smoke/CO detectors, replace batteries", "season": "spring", "interval_months": 6,
     "why": "NFPA recommends semi-annual battery replacement (daylight-saving weekends)."},
    # Summer
    {"id": "deck_seal", "task": "Inspect/reseal deck & fences", "season": "summer", "interval_months": 24,
     "why": "Sealing every 2-3 years prevents rot and doubles deck lifespan."},
    {"id": "dryer_vent", "task": "Clean dryer vent duct", "season": "summer", "interval_months": 12,
     "why": "Lint-clogged vents cause ~2,900 home fires per year (US Fire Admin)."},
    {"id": "irrigation", "task": "Check irrigation/sprinklers for leaks", "season": "summer", "interval_months": 12,
     "why": "A single stuck valve can waste thousands of gallons."},
    # Fall
    {"id": "furnace_service", "task": "Service furnace/heating before winter", "season": "fall", "interval_months": 12,
     "why": "Annual service prevents mid-winter failures and CO risks."},
    {"id": "gutters_fall", "task": "Clean gutters after leaf drop", "season": "fall", "interval_months": 6,
     "why": "Fall cleaning prevents ice dams in winter."},
    {"id": "winterize_spigots", "task": "Winterize exterior faucets/hoses", "season": "fall", "interval_months": 12,
     "why": "Burst pipes from freezing are among the costliest insurance claims."},
    {"id": "chimney", "task": "Chimney inspection/sweep (if used)", "season": "fall", "interval_months": 12,
     "why": "Creosote buildup causes chimney fires; annual inspection is NFPA 211 standard."},
    {"id": "weatherstrip", "task": "Check weatherstripping & caulk gaps", "season": "fall", "interval_months": 12,
     "why": "Air sealing saves 10-20% on heating bills."},
    # Winter
    {"id": "water_heater_flush", "task": "Flush water heater sediment", "season": "winter", "interval_months": 12,
     "why": "Sediment shortens tank life (typical lifespan 8-12 years)."},
    {"id": "pipe_insulation", "task": "Check pipe insulation in unheated spaces", "season": "winter", "interval_months": 12,
     "why": "Prevents freeze bursts in crawl spaces and garages."},
    {"id": "attic_check", "task": "Inspect attic for leaks/pests/insulation gaps", "season": "winter", "interval_months": 12,
     "why": "Early leak detection prevents mold remediation costs."},
]

VEHICLE_TEMPLATES = [
    {"id": "oil_change", "task": "Oil & filter change", "season": None, "interval_months": 6,
     "why": "Modern synthetic intervals are 5,000-10,000 mi or 6 months — check your OEM schedule."},
    {"id": "tire_rotation", "task": "Rotate tires", "season": None, "interval_months": 6,
     "why": "Rotation every 5,000-8,000 mi evens wear and extends tire life ~20%."},
    {"id": "brake_inspect", "task": "Brake inspection", "season": None, "interval_months": 12,
     "why": "Pads replaced early avoid rotor damage (2-4x the cost)."},
    {"id": "battery_test", "task": "Battery load test (3+ yr old battery)", "season": "fall", "interval_months": 12,
     "why": "Most batteries fail in the first cold snap after year 3."},
    {"id": "coolant_check", "task": "Check coolant & fluids", "season": None, "interval_months": 6,
     "why": "Low coolant is the leading cause of roadside breakdowns."},
    {"id": "registration", "task": "Vehicle registration renewal", "season": None, "interval_months": 12,
     "why": "Late renewal fines vary by state; set from your renewal date."},
    {"id": "wipers", "task": "Replace wiper blades", "season": "fall", "interval_months": 12,
     "why": "Rubber degrades in ~1 year of UV exposure."},
]

# Expected appliance lifespans (years) — industry standard estimates (NAHB study)
APPLIANCE_LIFESPANS = {
    "water_heater": 10, "hvac": 15, "furnace": 18, "roof_asphalt": 20,
    "refrigerator": 13, "dishwasher": 9, "washer": 10, "dryer": 13,
    "microwave": 9, "oven_range": 14, "garbage_disposal": 12,
    "garage_door_opener": 12, "sump_pump": 10, "gutters": 20,
}


class ChecklistItemUpdate(BaseModel):
    status: str  # done | pending | snoozed
    notes: Optional[str] = None


class ApplianceCreate(BaseModel):
    name: str
    appliance_type: str
    brand: Optional[str] = None
    purchase_date: Optional[str] = None   # YYYY-MM-DD
    warranty_end: Optional[str] = None    # YYYY-MM-DD
    notes: Optional[str] = None


class RepairCreate(BaseModel):
    category: str
    issue: str
    repair_date: Optional[str] = None
    cost: Optional[float] = None
    contractor: Optional[str] = None
    document_id: Optional[str] = None
    notes: Optional[str] = None


def _uid(user: Optional[UserDB]) -> str:
    return user.user_id if user else "anonymous"


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date '{s}' — use YYYY-MM-DD")


@router.get("/templates")
async def get_templates(category: str = "home"):
    """Research-backed checklist templates (home | vehicle)."""
    templates = HOME_TEMPLATES if category == "home" else VEHICLE_TEMPLATES
    return {"success": True, "category": category, "count": len(templates),
            "templates": templates}


@router.get("/checklist")
async def get_checklist(
    category: Optional[str] = None,
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    """
    User's live checklist: template tasks merged with their completion state.
    Items are grouped by season with due/overdue computed deterministically.
    """
    uid = _uid(user)
    result = await db.execute(
        select(MaintenanceItemDB).where(MaintenanceItemDB.user_id == uid)
    )
    user_items = {i.template_id: i for i in result.scalars().all() if i.template_id}

    now = datetime.utcnow()
    out = []
    for cat, templates in (("home", HOME_TEMPLATES), ("vehicle", VEHICLE_TEMPLATES)):
        if category and category != cat:
            continue
        for tpl in templates:
            item = user_items.get(tpl["id"])
            next_due = item.next_due if item and item.next_due else None
            status = item.status if item else "pending"
            overdue = bool(next_due and next_due < now and status != "done")
            # A done item becomes pending again after its interval elapses
            if item and item.status == "done" and next_due and next_due < now:
                status = "pending"
                overdue = True
            out.append({
                "template_id": tpl["id"],
                "category": cat,
                "task": tpl["task"],
                "season": tpl["season"],
                "interval_months": tpl["interval_months"],
                "why": tpl["why"],
                "status": status,
                "last_done": item.last_done.strftime("%Y-%m-%d") if item and item.last_done else None,
                "next_due": next_due.strftime("%Y-%m-%d") if next_due else None,
                "overdue": overdue,
            })

    done = sum(1 for i in out if i["status"] == "done")
    return {"success": True, "user_id": uid, "items": out,
            "progress": {"total": len(out), "done": done,
                         "overdue": sum(1 for i in out if i["overdue"])}}


@router.post("/checklist/{template_id}")
async def update_checklist_item(
    template_id: str,
    body: ChecklistItemUpdate,
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    """Mark a checklist item done/pending/snoozed; next_due computed from interval."""
    all_templates = {t["id"]: (t, cat) for cat, ts in
                     (("home", HOME_TEMPLATES), ("vehicle", VEHICLE_TEMPLATES)) for t in ts}
    if template_id not in all_templates:
        raise HTTPException(status_code=404, detail="Unknown checklist template")
    if body.status not in ("done", "pending", "snoozed"):
        raise HTTPException(status_code=400, detail="status must be done|pending|snoozed")

    tpl, cat = all_templates[template_id]
    uid = _uid(user)
    result = await db.execute(
        select(MaintenanceItemDB).where(
            MaintenanceItemDB.user_id == uid,
            MaintenanceItemDB.template_id == template_id)
    )
    item = result.scalar_one_or_none()
    now = datetime.utcnow()
    if not item:
        item = MaintenanceItemDB(
            user_id=uid, template_id=template_id, category=cat,
            season=tpl["season"], task_name=tpl["task"],
            interval_months=tpl["interval_months"],
        )
        db.add(item)

    item.status = body.status
    if body.notes:
        item.notes = body.notes
    if body.status == "done":
        item.last_done = now
        item.next_due = now + timedelta(days=tpl["interval_months"] * 30)
    elif body.status == "snoozed":
        item.next_due = now + timedelta(days=30)
    await db.commit()
    return {"success": True, "template_id": template_id, "status": body.status,
            "next_due": item.next_due.strftime("%Y-%m-%d") if item.next_due else None}


@router.get("/appliances")
async def list_appliances(
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    """Appliance registry with lifespan/warranty alerts (deterministic)."""
    uid = _uid(user)
    result = await db.execute(select(ApplianceDB).where(ApplianceDB.user_id == uid))
    now = datetime.utcnow()
    out = []
    for a in result.scalars().all():
        lifespan = a.expected_lifespan_years or APPLIANCE_LIFESPANS.get(a.appliance_type)
        age_years = round((now - a.purchase_date).days / 365.25, 1) if a.purchase_date else None
        pct_used = round(age_years / lifespan * 100, 0) if age_years and lifespan else None
        warranty_days = (a.warranty_end - now).days if a.warranty_end else None
        out.append({
            "id": a.id, "name": a.name, "type": a.appliance_type, "brand": a.brand,
            "age_years": age_years, "expected_lifespan_years": lifespan,
            "lifespan_used_pct": pct_used,
            "replacement_planning": pct_used is not None and pct_used >= 80,
            "warranty_end": a.warranty_end.strftime("%Y-%m-%d") if a.warranty_end else None,
            "warranty_days_left": warranty_days,
            "warranty_expiring_soon": warranty_days is not None and 0 <= warranty_days <= 60,
        })
    return {"success": True, "count": len(out), "appliances": out}


@router.post("/appliances")
async def add_appliance(
    body: ApplianceCreate,
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    """Register an appliance for lifespan and warranty tracking."""
    if body.appliance_type not in APPLIANCE_LIFESPANS and not body.appliance_type.strip():
        raise HTTPException(status_code=400, detail="appliance_type required")
    appliance = ApplianceDB(
        user_id=_uid(user),
        name=body.name.strip()[:120],
        appliance_type=body.appliance_type,
        brand=body.brand,
        purchase_date=_parse_date(body.purchase_date),
        warranty_end=_parse_date(body.warranty_end),
        expected_lifespan_years=APPLIANCE_LIFESPANS.get(body.appliance_type),
        notes=body.notes,
    )
    db.add(appliance)
    await db.commit()
    return {"success": True, "id": appliance.id,
            "expected_lifespan_years": appliance.expected_lifespan_years}


@router.delete("/appliances/{appliance_id}")
async def delete_appliance(
    appliance_id: int,
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(ApplianceDB).where(ApplianceDB.id == appliance_id,
                                  ApplianceDB.user_id == _uid(user)))
    appliance = result.scalar_one_or_none()
    if not appliance:
        raise HTTPException(status_code=404, detail="Appliance not found")
    await db.delete(appliance)
    await db.commit()
    return {"success": True}


@router.get("/repairs")
async def list_repairs(
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    """Repair history log with total spend."""
    result = await db.execute(
        select(RepairLogDB).where(RepairLogDB.user_id == _uid(user))
        .order_by(RepairLogDB.repair_date.desc().nullslast())
    )
    repairs = [{
        "id": r.id, "category": r.category, "issue": r.issue,
        "date": r.repair_date.strftime("%Y-%m-%d") if r.repair_date else None,
        "cost": r.cost, "contractor": r.contractor,
        "document_id": r.document_id, "notes": r.notes,
    } for r in result.scalars().all()]
    return {"success": True, "count": len(repairs),
            "total_spend": round(sum(r["cost"] or 0 for r in repairs), 2),
            "repairs": repairs}


@router.post("/repairs")
async def add_repair(
    body: RepairCreate,
    user: Optional[UserDB] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    """Log a repair (optionally linked to an uploaded receipt document)."""
    if not body.issue.strip():
        raise HTTPException(status_code=400, detail="issue is required")
    repair = RepairLogDB(
        user_id=_uid(user),
        category=body.category or "home",
        issue=body.issue.strip()[:300],
        repair_date=_parse_date(body.repair_date) or datetime.utcnow(),
        cost=body.cost,
        contractor=body.contractor,
        document_id=body.document_id,
        notes=body.notes,
    )
    db.add(repair)
    await db.commit()
    return {"success": True, "id": repair.id}


@router.post("/repairs/research")
async def research_repair(
    issue: str,
    user: Optional[UserDB] = Depends(get_optional_user),
):
    """
    OPT-IN AI research for a repair: typical cost range, DIY vs pro guidance,
    contractor questions. This is the only AI-powered endpoint in Maintenance.
    """
    if not issue.strip():
        raise HTTPException(status_code=400, detail="issue is required")
    try:
        from app.services.llm_client import generate_json
        prompt = (
            f"A homeowner reports this issue: {issue.strip()[:400]}\n\n"
            "Respond with practical research in JSON with keys: "
            "probable_causes (list), typical_cost_range_usd (string), "
            "diy_feasibility (easy|moderate|pro_only + one sentence), "
            "questions_for_contractor (list of 3), urgency (low|medium|high + why). "
            "Be honest about uncertainty; costs vary by region."
        )
        response = await generate_json(prompt, task="fast")
        return {"success": True, "issue": issue, "research": response,
                "note": "AI-generated research — verify costs with local quotes."}
    except Exception as e:
        logger.warning(f"repair research failed: {e}")
        return {"success": False, "issue": issue,
                "error": "AI research unavailable — try again later."}
