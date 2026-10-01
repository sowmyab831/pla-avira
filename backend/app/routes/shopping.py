"""Shopping assistant routes for deal tracking and price intelligence."""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session, UserDB
from app.routes.auth import get_current_user
from app.models.life_admin import OwnedWishlistDB
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, Field

from app.models.shopping import (
    Product, Deal, ShoppingRequest, ShoppingRecommendation, PriceAlert
)
from app.services.shopping_service import get_shopping_service
from app.services.smart_shopping import get_smart_shopping_service
from app.services import price_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shopping", tags=["shopping"])


class SearchRequest(BaseModel):
    """Shopping search request."""
    query: str = Field(..., min_length=1, max_length=300)
    category: Optional[str] = Field(None, max_length=80)
    max_price: Optional[float] = Field(None, ge=0, le=1_000_000)
    min_rating: Optional[float] = Field(None, ge=0, le=5)


@router.get("/smart-search")
async def smart_search(
    query: str = Query(..., description="Product to search for"),
    budget: Optional[float] = Query(None, description="Maximum budget"),
):
    """
    AI-powered smart shopping search.
    Finds the best value considering:
    - Prices across all major retailers
    - Available coupons and promo codes
    - Cashback opportunities
    - Retailer benefits (returns, warranty, shipping)
    Returns AI recommendation for best overall value.
    """
    smart_shopping = get_smart_shopping_service()
    return await smart_shopping.smart_search(query, budget)


@router.get("/search")
async def search_products_get(
    query: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Product category"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    min_rating: Optional[float] = Query(None, description="Minimum rating")
):
    """Search for products across multiple stores (GET)."""
    # Use smart shopping for better results
    smart_shopping = get_smart_shopping_service()
    result = await smart_shopping.smart_search(query, max_price)
    
    products = result.get("products", [])
    
    # Transform to expected format
    formatted_products = []
    for p in products:
        formatted_products.append({
            "name": p.get("name", query),
            "price": p.get("true_cost", p.get("price", 0)),
            "original_price": p.get("original_price", p.get("base_price")),
            "retailer": p.get("retailer", "Unknown"),
            "url": p.get("url", ""),
            "rating": p.get("rating", 4.0),
            "reviews": p.get("reviews", 0),
            "shipping": p.get("shipping", "Free"),
            "in_stock": p.get("in_stock", True),
            "savings": p.get("total_savings", 0),
            "coupon": p.get("best_coupon", {}).get("code") if p.get("best_coupon") else None,
            "cashback": p.get("cashback_rate", "0%"),
            "value_score": p.get("value_score", 50),
            "benefits": p.get("benefits", []),
        })
    
    # Filter by price and rating if specified
    if max_price:
        formatted_products = [p for p in formatted_products if p.get("price", 0) <= max_price]
    if min_rating:
        formatted_products = [p for p in formatted_products if p.get("rating", 0) >= min_rating]

    # Write-through price snapshots (own tracker — builds real history over time)
    snapshot_products = [
        {"title": p["name"], "price": p["price"], "retailer": p["retailer"], "url": p["url"]}
        for p in formatted_products
    ]
    tracked = await price_tracker.record_snapshots(snapshot_products)

    # Attach tracker keys so clients can request history/verdicts
    for p in formatted_products:
        p["tracker_key"] = price_tracker.product_key(p["name"], p["retailer"])

    return {
        "success": True,
        "query": query,
        "results": len(formatted_products),
        "snapshots_recorded": tracked,
        "products": formatted_products,
        "ai_recommendation": result.get("ai_recommendation"),
        "coupons": result.get("coupons_found", []),
        "potential_savings": result.get("potential_savings"),
    }


@router.post("/search")
async def search_products_post(request: SearchRequest):
    """Search for products across multiple stores (POST)."""
    return await search_products_get(
        query=request.query,
        category=request.category,
        max_price=request.max_price,
        min_rating=request.min_rating
    )


@router.get("/deals")
async def get_deals(category: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
    """Live deals from SlickDeals / DealNews / Reddit feeds (cached 15 min)."""
    from app.services.deals_crawler import get_latest_deals

    live = await get_latest_deals(q or category)
    deals = live.get("deals", [])
    source = "live"
    if not deals and not (q or category):
        deals = await get_shopping_service().get_deals(category)
        source = "fallback"
    return {
        "success": True,
        "category": category or "all",
        "query": q,
        "source": source,
        "sources": live.get("sources", []),
        "count": len(deals),
        "deals": deals[:limit],
    }


@router.get("/deals/watchlist")
async def deals_for_watchlist(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Match wishlist items against live deal feeds."""
    from app.services.deals_crawler import check_watchlist_deals
    rows = (await db.execute(select(OwnedWishlistDB).where(OwnedWishlistDB.user_id == user.user_id))).scalars().all()
    names = [i.name for i in rows]
    if not names:
        return {"success": True, "watchlist_items": 0, "items_with_deals": 0, "matches": {}}
    return await check_watchlist_deals(names)


@router.get("/product/{product_id}/history")
async def get_price_history(product_id: str, days: int = 365):
    """Real tracked price history: series, 1-year low, current vs low."""
    history = await price_tracker.get_history(product_id, days)
    return {
        "success": True,
        "product_id": product_id,
        "days": days,
        "history": history
    }


@router.get("/product/{product_id}/recommendation")
async def get_recommendation(product_id: str, category: str = "all"):
    """
    Deterministic BUY_NOW / WAIT / FAIR verdict from tracked history:
    price percentile + days-since-low + seasonal discount calendar. No AI.
    """
    verdict = await price_tracker.buy_verdict(product_id, category)
    return {
        "success": True,
        "product_id": product_id,
        "recommendation": verdict
    }


@router.post("/alerts")
async def create_price_alert(
    user_id: str,
    product_id: str,
    target_price: float
):
    """Create price alert for a product."""
    shopping = get_shopping_service()
    
    alert = await shopping.track_price(product_id, target_price, user_id)
    
    return {
        "success": True,
        "message": f"Price alert created for ${target_price:.2f}",
        "alert": alert
    }


@router.get("/stats")
async def get_shopping_stats():
    """Get shopping statistics."""
    return {
        "success": True,
        "total_products_tracked": 0,
        "active_deals": 0,
        "price_alerts": 0
    }


# ── Wishlist: track wanted items, find deals, price-drop analysis ──────────────

class WishlistAddRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    target_price: Optional[float] = Field(default=None, ge=0, le=1_000_000, allow_inf_nan=False)
    currency: Literal["USD", "INR"] = "USD"
    notes: str = Field(default="", max_length=2000)


def _wish(row):
    return {"id": row.id, "name": row.name, "target_price": row.target_minor / 100 if row.target_minor is not None else None,
            "currency": row.currency, "notes": row.notes, "added_at": row.created_at.isoformat(), "analysis": None}


@router.get("/wishlist")
async def get_wishlist(analyze: bool = True, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(OwnedWishlistDB).where(OwnedWishlistDB.user_id == user.user_id)
                            .order_by(OwnedWishlistDB.created_at.desc()))).scalars().all()
    return {"success": True, "items": [_wish(r) for r in rows], "count": len(rows), "good_deals_now": 0}


@router.post("/wishlist")
async def add_wishlist_item(request: WishlistAddRequest, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if not request.name.strip():
        raise HTTPException(400, "Item name is required")
    row = OwnedWishlistDB(user_id=user.user_id, name=request.name.strip(), currency=request.currency, notes=request.notes,
                         target_minor=int((Decimal(str(request.target_price))*100).quantize(Decimal("1"))) if request.target_price is not None else None)
    db.add(row); await db.commit(); await db.refresh(row)
    return {"success": True, "item": _wish(row)}


async def _owned_wish(db, user_id, item_id):
    row = (await db.execute(select(OwnedWishlistDB).where(OwnedWishlistDB.id == item_id, OwnedWishlistDB.user_id == user_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Wishlist item not found")
    return row


@router.delete("/wishlist/{item_id}")
async def remove_wishlist_item(item_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await _owned_wish(db, user.user_id, item_id)
    await db.delete(row); await db.commit()
    return {"success": True, "removed": item_id}


@router.get("/wishlist/{item_id}/analysis")
async def analyze_wishlist_item(item_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await _owned_wish(db, user.user_id, item_id)
    return {"success": True, "item": _wish(row), "analysis": {"ai_market_research":
        "Verified price history is not available for this exact item yet. Search for the model and compare merchant offers. No sale forecast or target-price claim has been generated."}}


# ── R4: tracked products + price alerts ──────────────────────────────────────

from app.models.ops import TrackedProductDB
from app.services.job_queue import enqueue


class TrackRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    retailer: Optional[str] = Field(None, max_length=120)
    url: Optional[str] = None
    currency: str = Field("USD", max_length=3)
    target_price: Optional[float] = Field(None, ge=0, le=10_000_000)
    drop_pct: int = Field(10, ge=1, le=90)


def _tracked(row: TrackedProductDB) -> dict:
    return {
        "id": row.id, "product_key": row.product_key, "title": row.title,
        "retailer": row.retailer, "url": row.url, "currency": row.currency,
        "target_price": (row.target_minor / 100) if row.target_minor is not None else None,
        "drop_pct": row.drop_pct,
        "baseline_price": (row.baseline_minor / 100) if row.baseline_minor is not None else None,
        "last_price": (row.last_minor / 100) if row.last_minor is not None else None,
        "active": row.active, "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/tracked")
async def list_tracked(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(
        select(TrackedProductDB).where(TrackedProductDB.user_id == user.user_id)
        .order_by(TrackedProductDB.created_at.desc())
    )).scalars().all()
    return {"success": True, "items": [_tracked(r) for r in rows], "count": len(rows)}


@router.post("/tracked")
async def track_product(request: TrackRequest, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    key = price_tracker.product_key(request.title, request.retailer or "")
    existing = (await db.execute(
        select(TrackedProductDB).where(
            TrackedProductDB.user_id == user.user_id,
            TrackedProductDB.product_key == key,
        )
    )).scalar_one_or_none()
    if existing:
        return {"success": True, "item": _tracked(existing), "already_tracked": True}
    # Baseline = latest snapshot we have for this product, if any.
    from app.database import PriceSnapshotDB
    snap = (await db.execute(
        select(PriceSnapshotDB.price).where(PriceSnapshotDB.product_key == key)
        .order_by(PriceSnapshotDB.captured_at.desc()).limit(1)
    )).first()
    row = TrackedProductDB(
        user_id=user.user_id, product_key=key, title=request.title.strip(),
        retailer=request.retailer, url=request.url, currency=request.currency.upper(),
        target_minor=int((Decimal(str(request.target_price)) * 100).quantize(Decimal("1"))) if request.target_price is not None else None,
        drop_pct=request.drop_pct,
        baseline_minor=int(round(snap[0] * 100)) if snap else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"success": True, "item": _tracked(row)}


@router.delete("/tracked/{item_id}")
async def untrack_product(item_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = (await db.execute(select(TrackedProductDB).where(
        TrackedProductDB.id == item_id, TrackedProductDB.user_id == user.user_id
    ))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Tracked product not found")
    row.active = False
    await db.commit()
    return {"success": True, "removed": item_id}


@router.post("/tracked/check")
async def check_tracked_now(user: UserDB = Depends(get_current_user)):
    """Enqueue an on-demand price check for this user's tracked products."""
    job_id = await enqueue("price.check", {"user_id": user.user_id})
    return {"success": True, "job_id": job_id, "status": "pending"}
