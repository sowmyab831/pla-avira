"""Pantry + shopping list + transactions (the receipt → kitchen → wallet loop)."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, get_session
from app.models.nexus import PantryItemDB, ReceiptDB, ShoppingItemDB, TransactionDB
from app.routes.auth import get_current_user
from app.services import nexus_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pantry", tags=["pantry"])


class PantryIn(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "count"
    category: Optional[str] = None
    expires_on: Optional[date] = None


class ShoppingIn(BaseModel):
    name: str
    quantity: Optional[str] = None
    reason: Optional[str] = None
    store_hint: Optional[str] = None


class TxIn(BaseModel):
    merchant: str
    amount: float
    category: str = "other"
    occurred_on: Optional[date] = None
    note: Optional[str] = None


def _p(i: PantryItemDB) -> dict:
    days_left = (i.expires_on - date.today()).days if i.expires_on else None
    return {"id": i.id, "name": i.name, "quantity": i.quantity, "unit": i.unit, "category": i.category,
            "purchased_on": i.purchased_on.isoformat() if i.purchased_on else None,
            "expires_on": i.expires_on.isoformat() if i.expires_on else None, "days_left": days_left,
            "status": i.status, "receipt_id": i.receipt_id}


@router.get("")
async def list_pantry(status: str = "in_stock", user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    q = select(PantryItemDB).where(PantryItemDB.user_id == user.user_id)
    if status != "all":
        q = q.where(PantryItemDB.status == status)
    res = await db.execute(q.order_by(PantryItemDB.expires_on.asc().nullslast(), PantryItemDB.name))
    items = [_p(i) for i in res.scalars().all()]
    by_cat: dict[str, list] = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    expiring = [it for it in items if it["days_left"] is not None and it["days_left"] <= 3]
    return {"items": items, "by_category": by_cat, "expiring_soon": expiring, "count": len(items)}


@router.post("")
async def add_pantry(body: PantryIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    cat = body.category or nexus_bus.categorize_item(body.name)
    exp = body.expires_on or (date.today() + timedelta(days=nexus_bus.PERISHABLE_DAYS.get(cat, 365)) if cat != "household" else None)
    row = PantryItemDB(user_id=user.user_id, name=body.name, normalized=nexus_bus.normalize_name(body.name), quantity=body.quantity,
                       unit=body.unit, category=cat, purchased_on=date.today(), expires_on=exp)
    db.add(row)
    await db.commit()
    return _p(row)


@router.patch("/{item_id}")
async def update_pantry(item_id: str, body: dict, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await db.get(PantryItemDB, item_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(404, "item not found")
    for k in ("name", "quantity", "unit", "category", "status"):
        if k in body:
            setattr(row, k, body[k])
    if "expires_on" in body:
        row.expires_on = date.fromisoformat(body["expires_on"]) if body["expires_on"] else None
    if body.get("status") == "low":
        await nexus_bus.emit(db, user.user_id, "pantry", "pantry.low", {"items": [{"name": row.name}]})
    await db.commit()
    return _p(row)


@router.delete("/{item_id}")
async def delete_pantry(item_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await db.get(PantryItemDB, item_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(404, "item not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.get("/receipts")
async def receipts(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(ReceiptDB).where(ReceiptDB.user_id == user.user_id).order_by(ReceiptDB.created_at.desc()).limit(50))
    return {"receipts": [{"id": r.id, "store": r.store, "total": r.total, "purchased_on": r.purchased_on.isoformat() if r.purchased_on else None,
                          "items": r.items, "category": r.category, "nexus_event_id": r.nexus_event_id} for r in res.scalars().all()]}


# ── Shopping list ────────────────────────────────────────────────────────────
@router.get("/shopping")
async def shopping(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(ShoppingItemDB).where(ShoppingItemDB.user_id == user.user_id).order_by(ShoppingItemDB.checked, ShoppingItemDB.created_at.desc()))
    return {"items": [{"id": s.id, "name": s.name, "quantity": s.quantity, "reason": s.reason, "store_hint": s.store_hint, "checked": s.checked}
                      for s in res.scalars().all()]}


@router.post("/shopping")
async def add_shopping(body: ShoppingIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = ShoppingItemDB(user_id=user.user_id, **body.model_dump())
    db.add(row)
    await db.commit()
    return {"id": row.id, "name": row.name}


@router.patch("/shopping/{item_id}")
async def toggle_shopping(item_id: str, body: dict, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await db.get(ShoppingItemDB, item_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(404, "item not found")
    if "checked" in body:
        row.checked = bool(body["checked"])
    if "name" in body:
        row.name = body["name"]
    await db.commit()
    return {"id": row.id, "checked": row.checked}


@router.delete("/shopping/{item_id}")
async def delete_shopping(item_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await db.execute(delete(ShoppingItemDB).where(ShoppingItemDB.id == item_id, ShoppingItemDB.user_id == user.user_id))
    await db.commit()
    return {"ok": True}


@router.post("/shopping/clear-checked")
async def clear_checked(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await db.execute(delete(ShoppingItemDB).where(ShoppingItemDB.user_id == user.user_id, ShoppingItemDB.checked == True))
    await db.commit()
    return {"ok": True}


# ── Transactions ─────────────────────────────────────────────────────────────
@router.get("/transactions")
async def transactions(days: int = 30, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    since = date.today() - timedelta(days=days)
    res = await db.execute(select(TransactionDB).where(TransactionDB.user_id == user.user_id, TransactionDB.occurred_on >= since)
                           .order_by(TransactionDB.occurred_on.desc()))
    rows = res.scalars().all()
    by_cat: dict[str, float] = {}
    for r in rows:
        by_cat[r.category] = round(by_cat.get(r.category, 0) + r.amount, 2)
    return {"transactions": [{"id": r.id, "occurred_on": r.occurred_on.isoformat(), "merchant": r.merchant, "amount": r.amount,
                              "category": r.category, "source": r.source} for r in rows],
            "total": round(sum(r.amount for r in rows), 2), "by_category": by_cat}


@router.post("/transactions")
async def add_tx(body: TxIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = TransactionDB(user_id=user.user_id, merchant=body.merchant, amount=body.amount, category=body.category,
                        occurred_on=body.occurred_on or date.today(), note=body.note, source="manual")
    db.add(row)
    await db.commit()
    return {"id": row.id}
