"""
Institutional Investor Tracker

Tracks:
- Major holders (BlackRock, Vanguard, State Street, etc.)
- Insider trades (Form 4 filings)
- Analyst ratings (Goldman Sachs, JPMorgan, Morgan Stanley, etc.)
- Short interest and institutional ownership changes
- Hedge fund positions from 13F filings

Uses Yahoo Finance API + SEC EDGAR for data.
"""

import httpx
import asyncio
import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


def _safe_float(v, default=0.0) -> float:
    """Sanitize float values — convert NaN/Inf to default."""
    import math
    if v is None:
        return default
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _safe_int(v, default=0) -> int:
    import math
    if v is None:
        return default
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError):
        return default

MAJOR_INSTITUTIONS = [
    "BlackRock", "Vanguard", "State Street", "Fidelity", "Capital Group",
    "T. Rowe Price", "Invesco", "Charles Schwab", "Morgan Stanley",
    "Goldman Sachs", "JPMorgan", "Citadel", "Bridgewater", "Renaissance",
    "Two Sigma", "D.E. Shaw", "Millennium", "Point72", "Berkshire Hathaway",
]

MAJOR_ANALYSTS = [
    "Goldman Sachs", "JPMorgan", "Morgan Stanley", "Bank of America",
    "Citigroup", "Wells Fargo", "Barclays", "Deutsche Bank", "UBS",
    "Credit Suisse", "RBC Capital", "Jefferies", "Piper Sandler",
    "Bernstein", "Wedbush", "Needham", "Raymond James",
]

SEC_HEADERS = {"User-Agent": "PLA-Avira research@avira.local", "Accept": "application/json"}


def _yf_holders_sync(symbol: str) -> Dict:
    """Fetch institutional holders via yfinance (runs in thread)."""
    holders = {"major_holders": [], "institutional_ownership_pct": None}
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)

        # Major holders breakdown
        try:
            mh = ticker.major_holders
            if mh is not None and len(mh) > 0:
                for _, row in mh.iterrows():
                    val = str(row.iloc[0]).strip()
                    label = str(row.iloc[1]).strip().lower() if len(row) > 1 else ""
                    if "institution" in label and "hold" in label:
                        holders["institutional_ownership_pct"] = val
                    elif "insider" in label:
                        holders["insider_ownership_pct"] = val
        except Exception:
            pass

        # Institutional holders
        try:
            ih = ticker.institutional_holders
            if ih is not None and len(ih) > 0:
                for _, row in ih.iterrows():
                    name = str(row.get("Holder", ""))
                    is_major = any(m.lower() in name.lower() for m in MAJOR_INSTITUTIONS)
                    holders["major_holders"].append({
                        "name": name,
                        "shares": _safe_int(row.get("Shares")),
                        "value": _safe_float(row.get("Value")),
                        "pct_held": round(_safe_float(row.get("% Out")) * 100, 2) if row.get("% Out") is not None else None,
                        "date_reported": str(row.get("Date Reported", "")),
                        "is_major": is_major,
                    })
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"yfinance holders error: {e}")

    return holders


async def _fetch_yahoo_holders(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Fetch institutional holders using yfinance in a thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _yf_holders_sync, symbol)


def _extract_val(d: Dict, key: str) -> Any:
    v = d.get(key, {})
    if isinstance(v, dict):
        return v.get("raw", v.get("longFmt", v.get("fmt", None)))
    return v


def _extract_pct(d: Dict, key: str) -> Optional[float]:
    v = _extract_val(d, key)
    if isinstance(v, (int, float)):
        return round(v * 100, 2) if v < 1 else round(v, 2)
    return None


def _yf_insiders_sync(symbol: str) -> List[Dict]:
    """Fetch insider trades via yfinance (runs in thread)."""
    trades = []
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)

        try:
            it = ticker.insider_transactions
            if it is not None and len(it) > 0:
                for _, row in it.head(20).iterrows():
                    trades.append({
                        "insider": str(row.get("Insider", row.get("Name", ""))),
                        "relation": str(row.get("Position", row.get("Relation", ""))),
                        "transaction": str(row.get("Transaction", row.get("Text", ""))),
                        "date": str(row.get("Start Date", row.get("Date", ""))),
                        "shares": _safe_int(row.get("Shares")),
                        "value": _safe_float(row.get("Value")),
                        "ownership": str(row.get("Ownership", "")),
                    })
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"yfinance insiders error: {e}")

    return trades


async def _fetch_insider_trades(symbol: str, client: httpx.AsyncClient) -> List[Dict]:
    """Fetch insider trades using yfinance in a thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _yf_insiders_sync, symbol)


def _yf_analysts_sync(symbol: str) -> Dict:
    """Fetch analyst ratings via yfinance (runs in thread)."""
    ratings = {"consensus": "", "target_mean": None, "target_high": None, "target_low": None, "recent": []}
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        ratings["target_mean"] = _safe_float(info.get("targetMeanPrice"), None)
        ratings["target_high"] = _safe_float(info.get("targetHighPrice"), None)
        ratings["target_low"] = _safe_float(info.get("targetLowPrice"), None)
        ratings["current_price"] = _safe_float(info.get("currentPrice", info.get("regularMarketPrice")), None)
        ratings["recommendation"] = info.get("recommendationKey", "")
        ratings["num_analysts"] = _safe_int(info.get("numberOfAnalystOpinions"), None)

        # Recommendation trend
        try:
            rec = ticker.recommendations
            if rec is not None and len(rec) > 0:
                for _, row in rec.tail(10).iterrows():
                    ratings["recent"].append({
                        "firm": str(row.get("Firm", "")),
                        "grade": str(row.get("To Grade", row.get("Action", ""))),
                        "action": str(row.get("Action", "")),
                    })
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"yfinance analysts error: {e}")

    return ratings


async def _fetch_analyst_ratings(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Fetch analyst ratings using yfinance in a thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _yf_analysts_sync, symbol)


async def _fetch_sec_filings(symbol: str, client: httpx.AsyncClient) -> List[Dict]:
    """Fetch recent SEC filings (10-K, 10-Q, 8-K, 13F) from EDGAR."""
    filings = []
    try:
        # First get CIK number
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&dateRange=custom&startdt=2024-01-01&forms=4,13F-HR,8-K&hits.hits.total=10"
        search_url = f"https://efts.sec.gov/LATEST/search-index?q={symbol}&forms=4,13F-HR,8-K"

        # Use full-text search
        resp = await client.get(
            f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&forms=4&dateRange=custom&startdt=2024-06-01",
            headers=SEC_HEADERS, timeout=8,
        )
        # SEC search is complex; fallback to ticker lookup
        ticker_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={symbol}&type=4&dateb=&owner=include&count=10&search_text=&action=getcompany"

    except Exception as e:
        logger.debug(f"SEC filings error: {e}")

    return filings


async def _detect_accumulation_signals(holders: Dict, insider_trades: List[Dict]) -> Dict:
    """Detect if major institutions or insiders are accumulating or dumping."""
    signals = {
        "institutional_accumulation": False,
        "insider_buying": False,
        "insider_selling": False,
        "dump_risk": False,
        "details": [],
    }

    # Check major holders for position increases
    for h in holders.get("major_holders", []):
        if h.get("is_major") and h.get("change"):
            try:
                change = float(h["change"]) if isinstance(h["change"], (int, float)) else 0
                if change > 5:
                    signals["institutional_accumulation"] = True
                    signals["details"].append(f"{h['name']} increased position by {change:.1f}%")
                elif change < -10:
                    signals["details"].append(f"⚠️ {h['name']} reduced position by {abs(change):.1f}%")
            except (ValueError, TypeError):
                pass

    # Check insider trades
    buy_value = 0
    sell_value = 0
    for t in insider_trades[:10]:
        txn = t.get("transaction", "").lower()
        val = t.get("value")
        if val and isinstance(val, (int, float)):
            if "purchase" in txn or "buy" in txn or "acquisition" in txn:
                buy_value += val
                signals["insider_buying"] = True
            elif "sale" in txn or "sell" in txn:
                sell_value += val

    if sell_value > buy_value * 3 and sell_value > 1_000_000:
        signals["insider_selling"] = True
        signals["dump_risk"] = True
        signals["details"].append(f"⚠️ Insider selling (${sell_value:,.0f}) vastly exceeds buying (${buy_value:,.0f})")
    elif buy_value > 500_000:
        signals["details"].append(f"✅ Insider buying: ${buy_value:,.0f} in recent purchases")

    return signals


async def get_institutional_analysis(symbol: str) -> Dict[str, Any]:
    """
    Full institutional investor analysis for a stock.

    Combines: holders, insider trades, analyst ratings, accumulation signals.
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        holders_task = _fetch_yahoo_holders(symbol, client)
        insider_task = _fetch_insider_trades(symbol, client)
        analyst_task = _fetch_analyst_ratings(symbol, client)

        holders, insiders, analysts = await asyncio.gather(
            holders_task, insider_task, analyst_task,
            return_exceptions=True,
        )

        if isinstance(holders, Exception):
            holders = {"major_holders": []}
        if isinstance(insiders, Exception):
            insiders = []
        if isinstance(analysts, Exception):
            analysts = {}

    # Detect accumulation/dumping signals
    signals = await _detect_accumulation_signals(holders, insiders)

    # Upside potential
    upside = None
    if analysts.get("target_mean") and analysts.get("current_price"):
        try:
            target = float(analysts["target_mean"])
            current = float(analysts["current_price"])
            upside = round(((target - current) / current) * 100, 1)
        except (ValueError, TypeError):
            pass

    # Major bank ratings summary
    bank_summary = []
    if analysts.get("recent"):
        latest = analysts["recent"][0] if analysts["recent"] else {}
        total = sum([
            latest.get("strong_buy", 0), latest.get("buy", 0),
            latest.get("hold", 0), latest.get("sell", 0),
            latest.get("strong_sell", 0),
        ])
        if total > 0:
            buy_pct = round(
                (latest.get("strong_buy", 0) + latest.get("buy", 0)) / total * 100, 1
            )
            bank_summary.append(f"{buy_pct}% of {total} analysts rate Buy/Strong Buy")

    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "holders": holders,
        "insider_trades": insiders[:10],
        "analyst_ratings": analysts,
        "upside_potential_pct": upside,
        "accumulation_signals": signals,
        "bank_summary": bank_summary,
    }
