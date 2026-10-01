"""
Watchlist Alerts & Earnings Calendar
=====================================

Features:
1. Price alerts — notify when a stock hits a target price
2. Earnings calendar — upcoming earnings dates for watchlist
3. Unusual volume alerts — detect volume spikes
4. News sentiment alerts — sudden sentiment shifts
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("AVIRA_DATA_DIR", "/tmp/avira_trading"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Price Alerts
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PriceAlert:
    id: str
    symbol: str
    condition: str  # "above" or "below"
    target_price: float
    created_at: str = ""
    triggered: bool = False
    triggered_at: Optional[str] = None
    current_price: Optional[float] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


def _alerts_path() -> Path:
    return _DATA_DIR / "price_alerts.json"


def load_alerts() -> List[PriceAlert]:
    p = _alerts_path()
    if p.exists():
        try:
            return [PriceAlert(**a) for a in json.loads(p.read_text())]
        except Exception:
            pass
    return []


def save_alerts(alerts: List[PriceAlert]) -> None:
    _alerts_path().write_text(json.dumps([asdict(a) for a in alerts], indent=2, default=str))


def create_alert(symbol: str, condition: str, target_price: float) -> PriceAlert:
    alerts = load_alerts()
    alert_id = f"ALT-{len(alerts) + 1:04d}"
    alert = PriceAlert(id=alert_id, symbol=symbol.upper(), condition=condition.lower(), target_price=target_price)
    alerts.append(alert)
    save_alerts(alerts)
    return alert


def delete_alert(alert_id: str) -> bool:
    alerts = load_alerts()
    before = len(alerts)
    alerts = [a for a in alerts if a.id != alert_id]
    if len(alerts) < before:
        save_alerts(alerts)
        return True
    return False


async def check_alerts() -> List[Dict[str, Any]]:
    """Check all active alerts against current prices."""
    alerts = load_alerts()
    active = [a for a in alerts if not a.triggered]
    if not active:
        return []

    symbols = list(set(a.symbol for a in active))

    def _get_prices():
        import yfinance as yf
        prices = {}
        for sym in symbols:
            try:
                tk = yf.Ticker(sym)
                hist = tk.history(period="1d")
                if not hist.empty:
                    prices[sym] = float(hist["Close"].iloc[-1])
            except Exception:
                pass
        return prices

    prices = await asyncio.get_event_loop().run_in_executor(None, _get_prices)

    triggered = []
    for alert in active:
        price = prices.get(alert.symbol)
        if price is None:
            continue
        alert.current_price = price
        hit = False
        if alert.condition == "above" and price >= alert.target_price:
            hit = True
        elif alert.condition == "below" and price <= alert.target_price:
            hit = True

        if hit:
            alert.triggered = True
            alert.triggered_at = datetime.now(timezone.utc).isoformat()
            triggered.append({
                "alert_id": alert.id,
                "symbol": alert.symbol,
                "condition": alert.condition,
                "target": alert.target_price,
                "current": price,
                "message": f"{alert.symbol} is now {'above' if alert.condition == 'above' else 'below'} ${alert.target_price:.2f} (current: ${price:.2f})",
            })

    save_alerts(alerts)
    return triggered


# ─────────────────────────────────────────────────────────────────────────────
# Earnings Calendar
# ─────────────────────────────────────────────────────────────────────────────

_earnings_cache: Dict[str, Any] = {}
_EARNINGS_TTL = 3600  # 1 hour


async def get_earnings_calendar(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get upcoming earnings dates for watchlist symbols."""
    from app.services.day_trading_scanner import DEFAULT_WATCHLIST
    symbols = symbols or DEFAULT_WATCHLIST

    cache_key = ",".join(sorted(symbols))
    now = time.time()
    if cache_key in _earnings_cache:
        ts, cached = _earnings_cache[cache_key]
        if now - ts < _EARNINGS_TTL:
            return cached

    def _fetch():
        import yfinance as yf
        results = []
        for sym in symbols:
            try:
                tk = yf.Ticker(sym)
                cal = tk.calendar
                if cal is not None and not cal.empty:
                    # calendar is a DataFrame with columns as dates
                    for col in cal.columns:
                        results.append({
                            "symbol": sym,
                            "date": str(col.date()) if hasattr(col, 'date') else str(col),
                            "event": "Earnings",
                        })
                # Also check earnings_dates
                try:
                    ed = tk.earnings_dates
                    if ed is not None and not ed.empty:
                        for idx in ed.index[:2]:  # Next 2
                            eps_est = ed.loc[idx].get("EPS Estimate")
                            results.append({
                                "symbol": sym,
                                "date": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                                "event": "Earnings Report",
                                "eps_estimate": float(eps_est) if eps_est and str(eps_est) != 'nan' else None,
                            })
                except Exception:
                    pass
            except Exception as e:
                logger.debug("earnings cal for %s: %s", sym, e)
        # Deduplicate by symbol+date
        seen = set()
        deduped = []
        for r in results:
            key = f"{r['symbol']}:{r['date']}"
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        deduped.sort(key=lambda x: x.get("date", ""))
        return deduped

    results = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "earnings": results,
    }
    _earnings_cache[cache_key] = (now, out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Volume Alerts (detect unusual volume)
# ─────────────────────────────────────────────────────────────────────────────

async def scan_unusual_volume(symbols: Optional[List[str]] = None, threshold: float = 2.0) -> List[Dict[str, Any]]:
    """Find stocks with volume significantly above average."""
    from app.services.day_trading_scanner import DEFAULT_WATCHLIST
    symbols = symbols or DEFAULT_WATCHLIST

    def _scan():
        import yfinance as yf
        import numpy as np
        results = []
        for sym in symbols:
            try:
                tk = yf.Ticker(sym)
                df = tk.history(period="1mo", interval="1d")
                if df.empty or len(df) < 5:
                    continue
                avg_vol = float(np.mean(df["Volume"].values[:-1]))
                curr_vol = float(df["Volume"].values[-1])
                if avg_vol > 0:
                    ratio = curr_vol / avg_vol
                    if ratio >= threshold:
                        results.append({
                            "symbol": sym,
                            "current_volume": int(curr_vol),
                            "avg_volume": int(avg_vol),
                            "ratio": round(ratio, 2),
                            "price": round(float(df["Close"].values[-1]), 2),
                            "change_pct": round(float((df["Close"].values[-1] - df["Close"].values[-2]) / df["Close"].values[-2] * 100), 2) if len(df) >= 2 else 0,
                        })
            except Exception:
                pass
        results.sort(key=lambda x: x["ratio"], reverse=True)
        return results

    return await asyncio.get_event_loop().run_in_executor(None, _scan)
