"""
Public Market Routes
────────────────────
Unauthenticated, read-only endpoints exposing NON-SENSITIVE aggregate market
data for the mobile app and public widgets:

  - Upcoming earnings calendar
  - Market + earnings digest text (for client-side WhatsApp share)

No user data, preferences, or PII are ever exposed here. Anything that touches
a user (notification prefs, WhatsApp delivery) stays under /api/notifications
behind JWT auth.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/market", tags=["public-market"])


@router.get("/earnings/upcoming")
async def public_upcoming_earnings(
    days: int = Query(30, ge=1, le=120, description="Days ahead to look"),
):
    """Public upcoming earnings calendar for major stocks."""
    from app.services.earnings_intelligence import get_upcoming_earnings
    data = await get_upcoming_earnings(days=days)
    return {"success": True, "count": len(data), "days_ahead": days, "earnings": data}


@router.get("/digest")
async def public_market_digest(
    earnings_days: int = Query(14, ge=1, le=90),
):
    """
    Public market + earnings digest text. The mobile app fetches this and
    shares it through the phone's own WhatsApp (via Linking) — keeping the
    user in full control and requiring no server-side messaging credentials.
    """
    from app.services.market_digest import build_market_digest
    digest = await build_market_digest(earnings_days=earnings_days)
    return {"success": True, **digest}


@router.get("/digest/watch")
async def public_watch_digest(
    symbols: str = Query(..., description="Comma-separated symbols, e.g. NVDA,AAPL,MSFT"),
    days: int = Query(30, ge=1, le=120),
):
    """Public earnings-watch digest for a user-supplied symbol list."""
    from app.services.market_digest import build_earnings_watchlist_digest
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:25]
    digest = await build_earnings_watchlist_digest(syms, days=days)
    return {"success": True, **digest}


@router.get("/earnings/{symbol}")
async def public_earnings_intelligence(symbol: str):
    """Public full 12-dimension earnings intelligence (non-sensitive market analysis)."""
    from fastapi import HTTPException
    symbol = symbol.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(400, "Invalid symbol")
    from app.services.earnings_intelligence import get_earnings_intelligence
    data = await get_earnings_intelligence(symbol)
    return {"success": True, **data}
