"""
Price-structure & breadth deep metrics — deterministic from OHLCV history.

Implements catalog groups 376–425: momentum, 52-week positioning, realized
volatility regime, drawdown, beta/correlation, universe breadth. No AI.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 900

_SECTOR_ETF = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV",
    "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP", "Energy": "XLE",
    "Industrials": "XLI", "Utilities": "XLU", "Real Estate": "XLRE",
    "Basic Materials": "XLB", "Communication Services": "XLC",
}


def compute_price_metrics(symbol: str, benchmark: str = "^GSPC") -> Dict[str, Any]:
    """Deterministic price-structure metrics from 1y of daily bars."""
    cache_key = f"{symbol.upper()}|{benchmark}"
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1y", interval="1d")
        if hist is None or hist.empty or len(hist) < 40:
            return {"symbol": symbol, "error": "insufficient_history"}
        closes = hist["Close"]
        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"price_metrics fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "error": "data_unavailable"}

    last = float(closes.iloc[-1])
    high_52w = float(closes.max())
    low_52w = float(closes.min())

    # Momentum 12-1 (skip most recent month to avoid reversal noise)
    mom_12_1 = None
    if len(closes) > 231:
        mom_12_1 = round((float(closes.iloc[-22]) / float(closes.iloc[-252]) - 1) * 100, 2) \
            if len(closes) >= 252 else \
            round((float(closes.iloc[-22]) / float(closes.iloc[0]) - 1) * 100, 2)

    # Realized volatility (annualized, 20d vs 60d for regime)
    rets = closes.pct_change().dropna()
    vol_20 = float(rets.tail(20).std()) * math.sqrt(252) * 100 if len(rets) >= 20 else None
    vol_60 = float(rets.tail(60).std()) * math.sqrt(252) * 100 if len(rets) >= 60 else None
    vol_regime = None
    if vol_20 is not None and vol_60 is not None:
        vol_regime = "expanding" if vol_20 > vol_60 * 1.2 else \
                     "contracting" if vol_20 < vol_60 * 0.8 else "stable"

    # Max drawdown over the year
    running_max = closes.cummax()
    drawdowns = (closes - running_max) / running_max
    max_dd = round(float(drawdowns.min()) * 100, 2)

    # 200DMA position
    dma200 = float(closes.tail(200).mean()) if len(closes) >= 200 else float(closes.mean())
    dma50 = float(closes.tail(50).mean()) if len(closes) >= 50 else None

    # Beta + correlation vs benchmark
    beta = corr = None
    try:
        bench = yf.Ticker(benchmark).history(period="1y", interval="1d")["Close"]
        joined = closes.pct_change().dropna().align(bench.pct_change().dropna(), join="inner")
        sr, br = joined
        if len(sr) > 40:
            corr = round(float(sr.corr(br)), 2)
            bvar = float(br.var())
            beta = round(float(sr.cov(br)) / bvar, 2) if bvar else None
    except Exception:
        pass

    sector = info.get("sector")
    result = {
        "symbol": symbol.upper(),
        "as_of": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "metrics": {
            "last_price": round(last, 2),
            "pct_from_52w_high": round((last / high_52w - 1) * 100, 2),
            "pct_from_52w_low": round((last / low_52w - 1) * 100, 2),
            "momentum_12_1_pct": mom_12_1,
            "realized_vol_20d_pct": round(vol_20, 1) if vol_20 is not None else None,
            "realized_vol_60d_pct": round(vol_60, 1) if vol_60 is not None else None,
            "vol_regime": vol_regime,
            "max_drawdown_1y_pct": max_dd,
            "above_200dma": last > dma200,
            "pct_vs_200dma": round((last / dma200 - 1) * 100, 2),
            "golden_cross": dma50 is not None and dma50 > dma200,
            "beta_1y": beta,
            "benchmark_correlation": corr,
            "sector": sector,
            "sector_etf": _SECTOR_ETF.get(sector),
        },
    }
    _CACHE[cache_key] = {"data": result, "ts": time.time()}
    return result


def compute_breadth(symbols: List[str]) -> Dict[str, Any]:
    """Universe breadth: % above 200DMA, advance/decline for a symbol list."""
    above = below = advancing = declining = 0
    checked = 0
    for sym in symbols[:30]:
        try:
            hist = yf.Ticker(sym).history(period="1y", interval="1d")["Close"]
            if hist.empty or len(hist) < 40:
                continue
            last = float(hist.iloc[-1])
            dma = float(hist.tail(min(200, len(hist))).mean())
            checked += 1
            if last > dma:
                above += 1
            else:
                below += 1
            if len(hist) >= 2 and last > float(hist.iloc[-2]):
                advancing += 1
            else:
                declining += 1
        except Exception:
            continue
    return {
        "symbols_checked": checked,
        "pct_above_200dma": round(above / checked * 100, 1) if checked else None,
        "advancers": advancing,
        "decliners": declining,
        "ad_ratio": round(advancing / declining, 2) if declining else None,
    }
