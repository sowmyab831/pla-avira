"""Deterministic household bills, renewals and deadlines. No LLM required."""
import calendar
from datetime import date, datetime, timedelta
from typing import Literal, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session, UserDB
from app.models.life_admin import CommitmentDB
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/life-admin", tags=["life-admin"])
KINDS = Literal["bill", "subscription", "return", "warranty", "document", "maintenance", "school", "care", "task", "refund", "claim"]


class CommitmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    kind: KINDS = "bill"
    country: Literal["US", "IN"] = "US"
    currency: Literal["USD", "INR"] = "USD"
    amount_minor: Optional[int] = Field(default=None, ge=0, le=100_000_000_000, strict=True)
    due_date: date = Field(ge=date(1900, 1, 1), le=date(2100, 12, 31))
    timezone: str = "America/New_York"
    recurrence: Literal["none", "weekly", "monthly", "yearly"] = "none"
    notes: str = Field(default="", max_length=2000)
    reference_url: Optional[str] = Field(default=None, max_length=2048)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a title")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid timezone")
        return value

    @field_validator("reference_url")
    @classmethod
    def safe_reference(cls, value):
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use an HTTPS provider or document link without credentials")
        return value

    @model_validator(mode="after")
    def currency_matches_country(self):
        if self.currency != {"US": "USD", "IN": "INR"}[self.country]:
            raise ValueError("Choose the currency for this commitment's country")
        return self


class CompletionIn(BaseModel):
    version: int = Field(ge=1)


def next_due(value: date, recurrence: str, anchor_day: int) -> date:
    if recurrence == "weekly":
        return value + timedelta(days=7)
    if recurrence == "yearly":
        year, month = value.year + 1, value.month
    elif recurrence == "monthly":
        year, month = value.year + (value.month == 12), value.month % 12 + 1
    else:
        return value
    return date(year, month, min(anchor_day, calendar.monthrange(year, month)[1]))


def serialize(row):
    today = datetime.now(ZoneInfo(row.timezone)).date()
    days = (row.due_date - today).days
    return {"id": row.id, "title": row.title, "kind": row.kind, "country": row.country,
            "currency": row.currency, "amount_minor": row.amount_minor, "due_date": row.due_date.isoformat(),
            "timezone": row.timezone, "recurrence": row.recurrence, "status": row.status,
            "notes": row.notes, "reference_url": row.reference_url, "version": row.version,
            "days_until_due": days, "urgency": "overdue" if days < 0 else "due_soon" if days <= 7 else "upcoming",
            "history": row.history or []}


@router.get("/commitments")
async def list_commitments(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(CommitmentDB).where(CommitmentDB.user_id == user.user_id)
                            .order_by(CommitmentDB.due_date, CommitmentDB.id))).scalars().all()
    items = [serialize(r) for r in rows]
    totals = {"USD": 0, "INR": 0}
    recoverable = {"USD": 0, "INR": 0}
    for item in items:
        if item["status"] == "open" and item["kind"] in ("refund", "claim"):
            recoverable[item["currency"]] += item["amount_minor"] or 0
        if item["status"] == "open" and item["kind"] in ("bill", "subscription") and item["days_until_due"] <= 30:
            totals[item["currency"]] += item["amount_minor"] or 0
    return {"items": items, "due_within_30_days_minor": totals, "pending_recovery_minor": recoverable, "delivery": "in_app", "ai_calls": 0}


@router.post("/commitments", status_code=201)
async def create_commitment(body: CommitmentIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = CommitmentDB(user_id=user.user_id, anchor_day=body.due_date.day, **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return serialize(row)


async def owned(db, user_id, item_id):
    row = (await db.execute(select(CommitmentDB).where(CommitmentDB.id == item_id,
                        CommitmentDB.user_id == user_id).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Commitment not found")
    return row


@router.put("/commitments/{item_id}")
async def edit_commitment(item_id: str, body: CommitmentIn, version: int,
                          user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await owned(db, user.user_id, item_id)
    if row.version != version:
        raise HTTPException(409, "This item changed. Refresh before saving.")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.anchor_day, row.version = body.due_date.day, row.version + 1
    await db.commit()
    return serialize(row)


@router.post("/commitments/{item_id}/complete")
async def complete_commitment(item_id: str, body: CompletionIn, user: UserDB = Depends(get_current_user),
                              db: AsyncSession = Depends(get_session)):
    row = await owned(db, user.user_id, item_id)
    if row.version != body.version:
        raise HTTPException(409, "This item changed. Refresh before completing it.")
    if row.status != "open":
        raise HTTPException(409, "This item is already completed")
    row.history = [*(row.history or []), {"due_date": row.due_date.isoformat(),
                   "completed_at": datetime.utcnow().isoformat() + "Z", "amount_minor": row.amount_minor,
                   "currency": row.currency, "confirmation": "user_reported"}][-120:]
    row.version += 1
    row.completed_at = datetime.utcnow()
    if row.recurrence == "none":
        row.status = "completed"
    else:
        row.due_date = next_due(row.due_date, row.recurrence, row.anchor_day)
    await db.commit()
    return serialize(row)
