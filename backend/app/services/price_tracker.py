"""
Price Tracker — own price-history database for shopping and travel.

Write-through snapshots on every search; deterministic buy-now verdicts from
percentile position, days-since-low and the retail seasonal calendar. No AI.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import PriceSnapshotDB, FareSnapshotDB, async_session_maker

logger = logging.getLogger(__name__)

# Retail seasonal calendar — months with historically deep discounts per category
_SEASONAL_EVENTS = [
    {"name": "Black Friday / Cyber Monday", "months": [11], "categories": ["all"]},
    {"name": "Prime Day (July)", "months": [7], "categories": ["all"]},
    {"name": "Back to school", "months": [8], "categories": ["electronics", "clothing"]},
    {"name": "January clearance", "months": [1], "categories": ["all"]},
    {"name": "Memorial Day", "months": [5], "categories": ["appliances", "mattress"]},
    {"name": "Labor Day", "months": [9], "categories": ["appliances", "mattress"]},
]


def product_key(title: str, retailer: str = "") -> str:
    """Normalize a product title+retailer into a stable snapshot key."""
    t = re.sub(r"[^a-z0-9 ]", "", (title or "").lower())
    t = re.sub(r"\s+", " ", t).strip()[:80]
    r = (retailer or "").lower().strip()
    return f"{t}|{r}" if r else t


async def record_snapshots(products: List[Dict[str, Any]], source: str = "search") -> int:
    """Write price snapshots for a list of search results. Returns count written."""
    written = 0
    try:
        async with async_session_maker() as session:
            for p in products:
                price = p.get("price")
                title = p.get("title") or p.get("name")
                if price is None or not title:
                    continue
                try:
                    price_f = float(str(price).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    continue
                if price_f <= 0:
                    continue
                retailer = p.get("retailer") or p.get("store") or p.get("source") or "unknown"
                session.add(PriceSnapshotDB(
                    product_key=product_key(title, retailer),
                    retailer=retailer,
                    title=str(title)[:300],
                    price=price_f,
                    currency=p.get("currency", "USD"),
                    url=p.get("url") or p.get("link"),
                    source=source,
                ))
                written += 1
            await session.commit()
    except Exception as e:
        logger.warning(f"price snapshot write failed: {e}")
    return written


async def get_history(key: str, days: int = 365) -> Dict[str, Any]:
    """Real price history for a product key: series + 1y low/high + current position."""
    since = datetime.utcnow() - timedelta(days=days)
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(PriceSnapshotDB)
                .where(PriceSnapshotDB.product_key == key,
                       PriceSnapshotDB.captured_at >= since)
                .order_by(PriceSnapshotDB.captured_at.asc())
            )
            rows = result.scalars().all()
    except Exception as e:
        logger.warning(f"price history read failed: {e}")
        rows = []

    if not rows:
        return {"product_key": key, "snapshots": 0, "history": [],
                "note": "No history yet — tracking starts with the first search."}

    prices = [r.price for r in rows]
    current = prices[-1]
    lowest = min(prices)
    highest = max(prices)
    lowest_row = next(r for r in rows if r.price == lowest)
    return {
        "product_key": key,
        "snapshots": len(rows),
        "tracked_since": rows[0].captured_at.strftime("%Y-%m-%d"),
        "current_price": current,
        "lowest_1y": lowest,
        "lowest_1y_date": lowest_row.captured_at.strftime("%Y-%m-%d"),
        "highest_1y": highest,
        "current_vs_low_pct": round((current - lowest) / lowest * 100, 1) if lowest else None,
        "history": [
            {"date": r.captured_at.strftime("%Y-%m-%d"), "price": r.price,
             "retailer": r.retailer, "source": r.source}
            for r in rows[-120:]
        ],
    }


def _next_seasonal_event(category: str = "all") -> Dict[str, Any]:
    """Next major discount event and days until it. Deterministic."""
    now = datetime.utcnow()
    best = None
    for event in _SEASONAL_EVENTS:
        if "all" not in event["categories"] and category not in event["categories"]:
            continue
        for month in event["months"]:
            year = now.year if month >= now.month else now.year + 1
            event_date = datetime(year, month, 15)
            days = (event_date - now).days
            if days >= 0 and (best is None or days < best["days_away"]):
                best = {"event": event["name"], "days_away": days}
    return best or {"event": None, "days_away": None}


async def buy_verdict(key: str, category: str = "all") -> Dict[str, Any]:
    """
    Deterministic BUY_NOW / WAIT / FAIR verdict:
    - price percentile within tracked history
    - days since the 1-year low
    - proximity of the next seasonal discount event
    Confidence scales with history depth. No AI.
    """
    hist = await get_history(key)
    seasonal = _next_seasonal_event(category)

    if hist["snapshots"] == 0:
        return {"verdict": "UNKNOWN", "confidence": "none",
                "reason": "No price history tracked yet for this product.",
                "next_seasonal_event": seasonal}

    prices = [h["price"] for h in hist["history"]]
    current = hist["current_price"]
    below = sum(1 for p in prices if p >= current)
    percentile = below / len(prices) * 100  # % of observations at-or-above current

    confidence = ("high" if hist["snapshots"] >= 30 and _span_days(hist) >= 90
                  else "medium" if hist["snapshots"] >= 10
                  else "low")

    seasonal_soon = seasonal["days_away"] is not None and seasonal["days_away"] <= 30

    if percentile >= 80 and not seasonal_soon:
        verdict, reason = "BUY_NOW", (
            f"Current price is cheaper than {percentile:.0f}% of tracked observations "
            f"(1y low: {hist['lowest_1y']})."
        )
    elif seasonal_soon:
        verdict, reason = "WAIT", (
            f"{seasonal['event']} is {seasonal['days_away']} days away — "
            f"prices in this category historically drop then."
        )
    elif percentile <= 40:
        verdict, reason = "WAIT", (
            f"Current price is higher than typical — {100 - percentile:.0f}% of "
            f"tracked observations were cheaper."
        )
    else:
        verdict, reason = "FAIR", "Current price is in the typical range for this product."

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "price_percentile": round(percentile, 1),
        "current_price": current,
        "lowest_1y": hist["lowest_1y"],
        "current_vs_low_pct": hist["current_vs_low_pct"],
        "next_seasonal_event": seasonal,
        "snapshots": hist["snapshots"],
    }


def _span_days(hist: Dict) -> int:
    try:
        first = datetime.strptime(hist["tracked_since"], "%Y-%m-%d")
        return (datetime.utcnow() - first).days
    except Exception:
        return 0


# ── Travel fares ──────────────────────────────────────────────────────────

async def record_fares(route: str, fares: List[Dict[str, Any]], travel_date: str = "") -> int:
    """Write fare snapshots for a flight search."""
    written = 0
    try:
        async with async_session_maker() as session:
            for f in fares:
                price = f.get("price")
                if price is None:
                    continue
                try:
                    price_f = float(str(price).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    continue
                if price_f <= 0:
                    continue
                session.add(FareSnapshotDB(
                    route=route.upper(),
                    travel_date=travel_date,
                    carrier=f.get("airline") or f.get("carrier"),
                    price=price_f,
                    currency=f.get("currency", "USD"),
                    source=f.get("source", "search"),
                ))
                written += 1
            await session.commit()
    except Exception as e:
        logger.warning(f"fare snapshot write failed: {e}")
    return written


async def get_fare_history(route: str, days: int = 365) -> Dict[str, Any]:
    """Fare history for a route with lowest tracked fare."""
    since = datetime.utcnow() - timedelta(days=days)
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(FareSnapshotDB)
                .where(FareSnapshotDB.route == route.upper(),
                       FareSnapshotDB.captured_at >= since)
                .order_by(FareSnapshotDB.captured_at.asc())
            )
            rows = result.scalars().all()
    except Exception as e:
        logger.warning(f"fare history read failed: {e}")
        rows = []

    if not rows:
        return {"route": route.upper(), "snapshots": 0, "history": [],
                "note": "No fare history yet — tracking starts with the first search."}

    prices = [r.price for r in rows]
    lowest_row = min(rows, key=lambda r: r.price)
    return {
        "route": route.upper(),
        "snapshots": len(rows),
        "tracked_since": rows[0].captured_at.strftime("%Y-%m-%d"),
        "current_low": min(r.price for r in rows[-20:]) if rows else None,
        "lowest_1y": lowest_row.price,
        "lowest_1y_date": lowest_row.captured_at.strftime("%Y-%m-%d"),
        "lowest_1y_carrier": lowest_row.carrier,
        "avg_1y": round(sum(prices) / len(prices), 2),
        "history": [
            {"date": r.captured_at.strftime("%Y-%m-%d"), "price": r.price,
             "carrier": r.carrier}
            for r in rows[-120:]
        ],
    }
