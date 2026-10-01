"""
NSE/BSE Client - Indian stock market data.

Provides real-time quotes, indices, and market data from
National Stock Exchange (NSE) and Bombay Stock Exchange (BSE).
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com/api"
BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


class NSEClient:
    """Async client for Indian market data (NSE + BSE)."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._cookies = None

    async def _get_cookies(self, client: httpx.AsyncClient) -> None:
        """NSE requires a session cookie from the homepage."""
        if self._cookies is None:
            try:
                resp = await client.get("https://www.nseindia.com", headers=HEADERS)
                self._cookies = resp.cookies
            except Exception:
                self._cookies = {}

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for an NSE symbol."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                await self._get_cookies(client)
                url = f"{NSE_BASE}/quote-equity?symbol={symbol}"
                resp = await client.get(url, headers=HEADERS, cookies=self._cookies)

                if resp.status_code != 200:
                    return self._fallback_quote(symbol)

                data = resp.json()
                price_info = data.get("priceInfo", {})

                return {
                    "symbol": symbol,
                    "exchange": "NSE",
                    "price": price_info.get("lastPrice", 0),
                    "change": price_info.get("change", 0),
                    "change_percent": price_info.get("pChange", 0),
                    "open": price_info.get("open", 0),
                    "high": price_info.get("intraDayHighLow", {}).get("max", 0),
                    "low": price_info.get("intraDayHighLow", {}).get("min", 0),
                    "prev_close": price_info.get("previousClose", 0),
                    "volume": data.get("securityWiseDP", {}).get("quantityTraded", 0),
                    "currency": "INR",
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"NSE quote error for {symbol}: {e}")
            return self._fallback_quote(symbol)

    async def get_indices(self) -> Dict[str, Any]:
        """Get major Indian market indices."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                await self._get_cookies(client)
                url = f"{NSE_BASE}/allIndices"
                resp = await client.get(url, headers=HEADERS, cookies=self._cookies)

                if resp.status_code != 200:
                    return self._fallback_indices()

                data = resp.json()
                indices = {}
                for idx in data.get("data", []):
                    name = idx.get("index", "")
                    if name in ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY NEXT 50"]:
                        indices[name] = {
                            "value": idx.get("last", 0),
                            "change": idx.get("percentChange", 0),
                            "open": idx.get("open", 0),
                            "high": idx.get("high", 0),
                            "low": idx.get("low", 0),
                        }

                return {"success": True, "indices": indices, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"NSE indices error: {e}")
            return self._fallback_indices()

    async def get_market_status(self) -> Dict[str, Any]:
        """Check if Indian markets are open."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                await self._get_cookies(client)
                url = f"{NSE_BASE}/marketStatus"
                resp = await client.get(url, headers=HEADERS, cookies=self._cookies)

                if resp.status_code == 200:
                    data = resp.json()
                    statuses = data.get("marketState", [])
                    return {
                        "success": True,
                        "markets": [
                            {"market": s.get("market"), "status": s.get("marketStatus")}
                            for s in statuses
                        ],
                    }
        except Exception as e:
            logger.error(f"NSE market status error: {e}")

        return {"success": True, "markets": [{"market": "NSE", "status": "Unknown"}]}

    async def get_top_gainers_losers(self) -> Dict[str, Any]:
        """Get top gainers and losers on NSE."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                await self._get_cookies(client)

                gainers_resp = await client.get(
                    f"{NSE_BASE}/live-analysis-variations?index=gainers",
                    headers=HEADERS, cookies=self._cookies,
                )
                losers_resp = await client.get(
                    f"{NSE_BASE}/live-analysis-variations?index=losers",
                    headers=HEADERS, cookies=self._cookies,
                )

                gainers = []
                losers = []

                if gainers_resp.status_code == 200:
                    for item in gainers_resp.json().get("NIFTY", {}).get("data", [])[:5]:
                        gainers.append({
                            "symbol": item.get("symbol"),
                            "price": item.get("ltp"),
                            "change_pct": item.get("perChange"),
                        })

                if losers_resp.status_code == 200:
                    for item in losers_resp.json().get("NIFTY", {}).get("data", [])[:5]:
                        losers.append({
                            "symbol": item.get("symbol"),
                            "price": item.get("ltp"),
                            "change_pct": item.get("perChange"),
                        })

                return {"success": True, "gainers": gainers, "losers": losers}
        except Exception as e:
            logger.error(f"NSE gainers/losers error: {e}")
            return {"success": True, "gainers": [], "losers": []}

    def _fallback_quote(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "exchange": "NSE",
            "price": 0,
            "change": 0,
            "change_percent": 0,
            "currency": "INR",
            "error": "Data temporarily unavailable",
        }

    def _fallback_indices(self) -> Dict[str, Any]:
        return {
            "success": True,
            "indices": {
                "NIFTY 50": {"value": 0, "change": 0},
                "NIFTY BANK": {"value": 0, "change": 0},
            },
            "error": "Live data temporarily unavailable",
        }
