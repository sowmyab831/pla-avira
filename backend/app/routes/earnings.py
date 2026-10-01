"""
Earnings Intelligence API Routes
─────────────────────────────────
Comprehensive pre-earnings analysis with LLM synthesis.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import UserDB
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/earnings", tags=["earnings"])


@router.get("/upcoming")
async def upcoming_earnings(
    days: int = Query(14, ge=1, le=90, description="Days ahead to look"),
    current_user: UserDB = Depends(get_current_user),
):
    """Get upcoming earnings dates for major stocks."""
    from app.services.earnings_intelligence import get_upcoming_earnings
    data = await get_upcoming_earnings(days=days)
    return {"success": True, "count": len(data), "days_ahead": days, "earnings": data}


@router.get("/intelligence/{symbol}")
async def earnings_intelligence(
    symbol: str,
    current_user: UserDB = Depends(get_current_user),
):
    """
    Full 12-dimension earnings intelligence report for a symbol.

    Analyses: financials, SEC filings, insider trading, buybacks, leadership,
    competitors, supply chain, geopolitics, analyst consensus, social sentiment,
    options positioning, macro context — then synthesises with LLM.
    """
    symbol = symbol.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(400, "Invalid symbol")

    from app.services.earnings_intelligence import get_earnings_intelligence
    data = await get_earnings_intelligence(symbol)
    return {"success": True, **data}


@router.get("/quick/{symbol}")
async def quick_earnings_preview(
    symbol: str,
    current_user: UserDB = Depends(get_current_user),
):
    """Lighter-weight earnings preview — financials + analyst + sentiment only."""
    symbol = symbol.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(400, "Invalid symbol")

    from app.services.earnings_intelligence import (
        _get_financials,
        _get_analyst_consensus,
        _get_social_sentiment,
        _get_options_positioning,
    )
    import asyncio, httpx

    async with httpx.AsyncClient(follow_redirects=True) as client:
        financials, analyst, sentiment, options = await asyncio.gather(
            _get_financials(symbol),
            _get_analyst_consensus(symbol),
            _get_social_sentiment(symbol, client),
            _get_options_positioning(symbol),
            return_exceptions=True,
        )

    return {
        "success": True,
        "symbol": symbol,
        "financials": financials if not isinstance(financials, Exception) else {},
        "analyst": analyst if not isinstance(analyst, Exception) else {},
        "sentiment": sentiment if not isinstance(sentiment, Exception) else {},
        "options": options if not isinstance(options, Exception) else {},
    }
