"""
Yahoo Finance Client - Real-time US stock data.

Provides price quotes, historical data, options chains, and company info
using Yahoo Finance's public API endpoints.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

YAHOO_BASE = "https://query1.finance.yahoo.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


class YFinanceClient:
    """Async Yahoo Finance client for US market data."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for a symbol."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = f"{YAHOO_BASE}/v8/finance/chart/{symbol}"
                resp = await client.get(
                    url,
                    params={"interval": "1d", "range": "5d"},
                    headers=HEADERS,
                )
                if resp.status_code != 200:
                    return self._empty_quote(symbol)

                data = resp.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                meta = result.get("meta", {})

                current = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("chartPreviousClose", current)
                change = current - prev_close if current and prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0

                return {
                    "symbol": symbol,
                    "price": current,
                    "previous_close": prev_close,
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "currency": meta.get("currency", "USD"),
                    "exchange": meta.get("exchangeName", ""),
                    "market_state": meta.get("marketState", ""),
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"YFinance quote error for {symbol}: {e}")
            return self._empty_quote(symbol)

    async def get_historical(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical price data."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = f"{YAHOO_BASE}/v8/finance/chart/{symbol}"
                resp = await client.get(
                    url,
                    params={"interval": interval, "range": period},
                    headers=HEADERS,
                )
                if resp.status_code != 200:
                    return {"symbol": symbol, "prices": [], "error": f"HTTP {resp.status_code}"}

                data = resp.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                timestamps = result.get("timestamp", [])
                indicators = result.get("indicators", {})
                quote = indicators.get("quote", [{}])[0]

                prices = []
                opens = quote.get("open", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])
                closes = quote.get("close", [])
                volumes = quote.get("volume", [])

                for i, ts in enumerate(timestamps):
                    if i < len(closes) and closes[i] is not None:
                        prices.append({
                            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                            "open": opens[i] if i < len(opens) else None,
                            "high": highs[i] if i < len(highs) else None,
                            "low": lows[i] if i < len(lows) else None,
                            "close": closes[i],
                            "volume": volumes[i] if i < len(volumes) else 0,
                        })

                return {
                    "symbol": symbol,
                    "period": period,
                    "interval": interval,
                    "prices": prices,
                    "count": len(prices),
                }
        except Exception as e:
            logger.error(f"YFinance historical error for {symbol}: {e}")
            return {"symbol": symbol, "prices": [], "error": str(e)}

    async def get_company_info(self, symbol: str) -> Dict[str, Any]:
        """Get company profile and fundamentals."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = f"{YAHOO_BASE}/v10/finance/quoteSummary/{symbol}"
                resp = await client.get(
                    url,
                    params={"modules": "assetProfile,financialData,defaultKeyStatistics"},
                    headers=HEADERS,
                )
                if resp.status_code != 200:
                    return {"symbol": symbol, "error": f"HTTP {resp.status_code}"}

                data = resp.json()
                result = data.get("quoteSummary", {}).get("result", [{}])[0]

                profile = result.get("assetProfile", {})
                financials = result.get("financialData", {})
                stats = result.get("defaultKeyStatistics", {})

                return {
                    "symbol": symbol,
                    "name": profile.get("longBusinessSummary", "")[:200],
                    "sector": profile.get("sector", ""),
                    "industry": profile.get("industry", ""),
                    "employees": profile.get("fullTimeEmployees"),
                    "market_cap": financials.get("marketCap", {}).get("raw"),
                    "pe_ratio": stats.get("forwardPE", {}).get("raw"),
                    "eps": stats.get("trailingEps", {}).get("raw"),
                    "dividend_yield": stats.get("dividendYield", {}).get("raw"),
                    "beta": stats.get("beta", {}).get("raw"),
                    "52w_high": stats.get("fiftyTwoWeekHigh", {}).get("raw"),
                    "52w_low": stats.get("fiftyTwoWeekLow", {}).get("raw"),
                }
        except Exception as e:
            logger.error(f"YFinance company info error for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    async def get_options_expirations(self, symbol: str) -> List[str]:
        """Get available options expiration dates."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = f"{YAHOO_BASE}/v7/finance/options/{symbol}"
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                timestamps = data.get("optionChain", {}).get("result", [{}])[0].get("expirationDates", [])
                return [datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in timestamps]
        except Exception as e:
            logger.error(f"YFinance options expirations error for {symbol}: {e}")
            return []

    def _empty_quote(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "price": 0,
            "change": 0,
            "change_percent": 0,
            "error": "Data unavailable",
        }
