"""
NSE India public-endpoint fallback client.

Used when yfinance lags or fails for Indian indices/movers. NSE requires a
cookie bootstrap from the homepage before hitting JSON APIs. All responses are
cached in-process for 5 minutes and every fetch degrades gracefully to None so
callers can fall back to yfinance-only behavior.
"""
from __future__ import annotations

import logging
import time as time_mod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://www.nseindia.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_get(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if entry and (time_mod.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: Any) -> None:
    _CACHE[key] = {"data": data, "ts": time_mod.time()}


async def _get_json(path: str) -> Optional[Any]:
    """Cookie-bootstrapped GET with graceful failure."""
    cached = _cache_get(path)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as client:
            # Bootstrap cookies (NSE blocks cookie-less API hits)
            await client.get(_BASE)
            resp = await client.get(f"{_BASE}{path}")
            if resp.status_code == 200:
                data = resp.json()
                _cache_set(path, data)
                return data
            logger.warning(f"NSE API {path} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"NSE API {path} failed: {e}")
    return None


async def get_index_quotes() -> Optional[List[Dict]]:
    """Major NSE indices (NIFTY 50, BANK NIFTY, etc.) — real-time-ish."""
    data = await _get_json("/api/allIndices")
    if not data:
        return None
    wanted = {"NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY NEXT 50", "INDIA VIX"}
    out = []
    for idx in data.get("data", []):
        if idx.get("index") in wanted:
            out.append({
                "name": idx.get("index"),
                "last": idx.get("last"),
                "change": idx.get("variation"),
                "change_percent": idx.get("percentChange"),
                "source": "nse",
            })
    return out or None


async def get_top_movers() -> Optional[Dict[str, List[Dict]]]:
    """NIFTY 50 top gainers and losers."""
    data = await _get_json("/api/equity-stockIndices?index=NIFTY%2050")
    if not data:
        return None
    rows = []
    for row in data.get("data", []):
        sym = row.get("symbol")
        if not sym or sym == "NIFTY 50":
            continue
        rows.append({
            "symbol": sym,
            "last_price": row.get("lastPrice"),
            "change_percent": row.get("pChange"),
            "day_high": row.get("dayHigh"),
            "day_low": row.get("dayLow"),
            "year_high": row.get("yearHigh"),
            "year_low": row.get("yearLow"),
            "source": "nse",
        })
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("change_percent") or 0, reverse=True)
    return {"gainers": rows[:5], "losers": rows[-5:][::-1]}


async def get_quote(symbol: str) -> Optional[Dict]:
    """Single equity quote from NSE (symbol without .NS suffix)."""
    base = symbol.upper().replace(".NS", "").replace(".BO", "")
    data = await _get_json(f"/api/quote-equity?symbol={base}")
    if not data:
        return None
    price_info = data.get("priceInfo") or {}
    if not price_info.get("lastPrice"):
        return None
    return {
        "symbol": base,
        "last_price": price_info.get("lastPrice"),
        "change": price_info.get("change"),
        "change_percent": price_info.get("pChange"),
        "day_high": (price_info.get("intraDayHighLow") or {}).get("max"),
        "day_low": (price_info.get("intraDayHighLow") or {}).get("min"),
        "year_high": (price_info.get("weekHighLow") or {}).get("max"),
        "year_low": (price_info.get("weekHighLow") or {}).get("min"),
        "source": "nse",
    }
