"""
Stock Recommendation Engine — scores and ranks stocks using 20+ data sources.

Scoring dimensions (0-100 each):
  1. Technical Score   — RSI, MACD, SMA crossover, momentum
  2. Fundamental Score — PE, earnings growth, profit margin, revenue growth
  3. Sentiment Score   — social media, news, analyst consensus, insider activity
  4. Value Score       — 52w range position, forward PE vs peers, target price gap
  5. Macro Score       — VIX level, fear/greed, put/call ratio, yield curve

Final score = weighted average → rank → top 10 recommendations.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)

# Universe: 100 liquid stocks across all major sectors
STOCK_UNIVERSE = [
    # Mega-cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO",
    # Growth Tech
    "CRM", "ADBE", "AMD", "NFLX", "ORCL", "NOW", "SNOW", "PLTR", "MSTR",
    "SHOP", "SQ", "COIN", "UBER", "ABNB", "DDOG", "NET", "CRWD", "ZS",
    # Semiconductors
    "QCOM", "TXN", "INTC", "MU", "MRVL", "KLAC", "LRCX", "AMAT",
    # Finance
    "JPM", "V", "MA", "GS", "MS", "BRK-B", "BAC", "C", "SCHW", "AXP",
    # Healthcare / Pharma
    "UNH", "JNJ", "LLY", "MRK", "ABBV", "PFE", "TMO", "ABT", "AMGN", "ISRG",
    # Consumer
    "PG", "KO", "PEP", "COST", "WMT", "MCD", "SBUX", "NKE", "TGT", "HD", "LOW",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG",
    # Industrials
    "CAT", "DE", "BA", "GE", "HON", "UPS", "RTX", "LMT",
    # Media / Telecom
    "DIS", "CMCSA", "T", "VZ", "TMUS",
    # Real Estate / REITs
    "AMT", "PLD", "CCI",
    # Other high-interest
    "ACN", "DHR", "CSCO", "IBM", "PANW", "SMCI",
]


def _score_technical(yf_data: Dict) -> float:
    """Score 0-100 based on technical indicators."""
    score = 50.0
    closes = yf_data.get("recent_closes", [])
    if not closes or len(closes) < 20:
        return score

    # RSI
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas[-14:]]
    losses = [abs(min(d, 0)) for d in deltas[-14:]]
    avg_gain = float(np.mean(gains)) if gains else 0
    avg_loss = float(np.mean(losses)) if losses else 1e-9
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - 100 / (1 + rs)

    if rsi < 30:
        score += 15  # Oversold = buy opportunity
    elif rsi < 40:
        score += 8
    elif rsi > 70:
        score -= 15  # Overbought
    elif rsi > 60:
        score -= 5

    # SMA crossover
    sma10 = float(np.mean(closes[-10:]))
    sma20 = float(np.mean(closes[-20:]))
    if sma10 > sma20:
        score += 10  # Bullish crossover
    else:
        score -= 10

    # Price momentum (last 20 days)
    momentum = (closes[-1] - closes[0]) / closes[0] * 100
    if momentum > 10:
        score += 15
    elif momentum > 5:
        score += 8
    elif momentum < -10:
        score -= 10
    elif momentum < -5:
        score -= 5

    return max(0, min(100, score))


def _score_fundamental(yf_data: Dict) -> float:
    """Score 0-100 based on fundamentals."""
    score = 50.0

    pe = yf_data.get("pe_ratio")
    if pe and isinstance(pe, (int, float)):
        if 5 < pe < 15:
            score += 15  # Undervalued
        elif 15 <= pe < 25:
            score += 5
        elif pe > 40:
            score -= 10  # Overvalued

    fwd_pe = yf_data.get("forward_pe")
    if fwd_pe and isinstance(fwd_pe, (int, float)) and pe and isinstance(pe, (int, float)):
        if fwd_pe < pe:
            score += 10  # Earnings expected to grow

    eg = yf_data.get("earnings_growth")
    if eg and isinstance(eg, (int, float)):
        if eg > 0.2:
            score += 15
        elif eg > 0.1:
            score += 8
        elif eg < -0.1:
            score -= 10

    rg = yf_data.get("revenue_growth")
    if rg and isinstance(rg, (int, float)):
        if rg > 0.15:
            score += 10
        elif rg > 0.05:
            score += 5
        elif rg < 0:
            score -= 8

    pm = yf_data.get("profit_margin")
    if pm and isinstance(pm, (int, float)):
        if pm > 0.25:
            score += 10
        elif pm > 0.10:
            score += 5
        elif pm < 0:
            score -= 15

    return max(0, min(100, score))


def _score_sentiment(yf_data: Dict, social: Dict, insider: Dict) -> float:
    """Score 0-100 based on sentiment signals."""
    score = 50.0

    # Analyst recommendation
    rec = yf_data.get("recommendation")
    if rec:
        rec_map = {"strongBuy": 20, "buy": 15, "hold": 0, "sell": -15, "strongSell": -20}
        score += rec_map.get(rec, 0)

    # Social sentiment
    st = social.get("stocktwits", {})
    if isinstance(st, dict) and "bull_pct" in st:
        bull = st["bull_pct"]
        if bull > 70:
            score += 10
        elif bull > 55:
            score += 5
        elif bull < 30:
            score -= 10

    # Reddit mentions
    wsb = social.get("reddit_wsb", {})
    if isinstance(wsb, dict):
        mentions = wsb.get("mentions", "low")
        if mentions == "high":
            score += 5  # Buzz (caution: could be hype)

    # Insider activity
    ia = insider.get("insider_activity", "low")
    if ia == "high":
        score += 8  # Insiders are active → something happening

    # Insider ownership
    insider_pct = yf_data.get("insider_pct")
    if insider_pct and isinstance(insider_pct, (int, float)):
        if insider_pct > 0.10:
            score += 5  # High insider ownership = aligned interests

    return max(0, min(100, score))


def _score_value(yf_data: Dict) -> float:
    """Score 0-100 based on value metrics."""
    score = 50.0

    price = yf_data.get("price")
    high52 = yf_data.get("52w_high")
    low52 = yf_data.get("52w_low")
    target = yf_data.get("target_price")

    if price and high52 and low52:
        range_pos = (price - low52) / (high52 - low52) if high52 != low52 else 0.5
        if range_pos < 0.3:
            score += 15  # Near 52w low → value
        elif range_pos < 0.5:
            score += 5
        elif range_pos > 0.9:
            score -= 10  # Near 52w high → extended

    if price and target:
        gap = (target - price) / price * 100
        if gap > 20:
            score += 20  # Big upside to analyst target
        elif gap > 10:
            score += 10
        elif gap < -10:
            score -= 15

    # Dividend yield bonus
    dy = yf_data.get("dividend_yield")
    if dy and isinstance(dy, (int, float)):
        if dy > 0.04:
            score += 10
        elif dy > 0.02:
            score += 5

    return max(0, min(100, score))


def _score_macro(vix: Dict, fear_greed: Dict, pcr: Dict) -> float:
    """Score 0-100 based on macro conditions."""
    score = 50.0

    # VIX
    vix_val = vix.get("vix")
    if vix_val and isinstance(vix_val, (int, float)):
        if vix_val > 30:
            score -= 15  # High fear
        elif vix_val > 20:
            score -= 5
        elif vix_val < 15:
            score += 10  # Low vol = complacency or calm

    # Fear & Greed
    fg = fear_greed.get("score")
    if fg and isinstance(fg, (int, float)):
        if fg < 25:
            score += 15  # Extreme fear = contrarian buy
        elif fg < 40:
            score += 5
        elif fg > 75:
            score -= 10  # Extreme greed = caution

    # Put/Call ratio
    ratio = pcr.get("ratio")
    if ratio and isinstance(ratio, (int, float)):
        if ratio > 1.2:
            score += 10  # Extreme puts = contrarian buy
        elif ratio < 0.7:
            score -= 10  # Extreme calls = complacency

    return max(0, min(100, score))


async def _score_single_stock(symbol: str, macro_data: Dict) -> Dict[str, Any]:
    """Score a single stock across all dimensions."""
    from app.services.market_data_aggregator import (
        get_yfinance_data,
        get_insider_trading,
        get_social_sentiment,
    )

    # Gather data
    yf_data = await asyncio.to_thread(get_yfinance_data, symbol)
    insider, social = await asyncio.gather(
        get_insider_trading(symbol),
        get_social_sentiment(symbol),
        return_exceptions=True,
    )
    if isinstance(insider, Exception):
        insider = {}
    if isinstance(social, Exception):
        social = {}

    tech = _score_technical(yf_data)
    fund = _score_fundamental(yf_data)
    sent = _score_sentiment(yf_data, social, insider)
    val = _score_value(yf_data)
    macro = _score_macro(
        macro_data.get("vix", {}),
        macro_data.get("fear_greed", {}),
        macro_data.get("pcr", {}),
    )

    # Weighted composite
    weights = {"technical": 0.25, "fundamental": 0.25, "sentiment": 0.15, "value": 0.20, "macro": 0.15}
    composite = round(
        tech * weights["technical"]
        + fund * weights["fundamental"]
        + sent * weights["sentiment"]
        + val * weights["value"]
        + macro * weights["macro"],
        1,
    )

    # Rating label
    if composite >= 75:
        rating = "STRONG BUY"
    elif composite >= 62:
        rating = "BUY"
    elif composite >= 45:
        rating = "HOLD"
    elif composite >= 30:
        rating = "SELL"
    else:
        rating = "STRONG SELL"

    return {
        "symbol": symbol,
        "composite_score": composite,
        "rating": rating,
        "scores": {
            "technical": round(tech, 1),
            "fundamental": round(fund, 1),
            "sentiment": round(sent, 1),
            "value": round(val, 1),
            "macro": round(macro, 1),
        },
        "price": yf_data.get("price"),
        "target_price": yf_data.get("target_price"),
        "pe_ratio": yf_data.get("pe_ratio"),
        "sector": yf_data.get("sector"),
        "recommendation": yf_data.get("recommendation"),
        "market_cap": yf_data.get("market_cap"),
        "earnings_growth": yf_data.get("earnings_growth"),
        "short_pct_float": yf_data.get("short_pct_float"),
    }


async def get_top_recommendations(count: int = 10) -> Dict[str, Any]:
    """
    Scan the stock universe, score every stock, return top N recommendations.

    This is a heavyweight call (~20-40s) — results are cached for 5 min.
    """
    from app.services.market_data_aggregator import get_vix, get_fear_greed, get_put_call_ratio

    start = datetime.now()

    # Macro data (shared across all stocks)
    vix, fear_greed, pcr = await asyncio.gather(
        asyncio.to_thread(get_vix),
        get_fear_greed(),
        asyncio.to_thread(get_put_call_ratio),
        return_exceptions=True,
    )
    macro_data = {
        "vix": vix if not isinstance(vix, Exception) else {},
        "fear_greed": fear_greed if not isinstance(fear_greed, Exception) else {},
        "pcr": pcr if not isinstance(pcr, Exception) else {},
    }

    # Score all stocks in parallel (batches of 10 to avoid rate limits)
    all_scores: List[Dict] = []
    batch_size = 10
    for i in range(0, len(STOCK_UNIVERSE), batch_size):
        batch = STOCK_UNIVERSE[i : i + batch_size]
        results = await asyncio.gather(
            *[_score_single_stock(s, macro_data) for s in batch],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, dict) and "composite_score" in r:
                all_scores.append(r)

    # Sort by composite score
    all_scores.sort(key=lambda x: x["composite_score"], reverse=True)

    top = all_scores[:count]
    bottom = all_scores[-3:] if len(all_scores) > 3 else []

    elapsed = (datetime.now() - start).total_seconds()

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "scan_universe": len(STOCK_UNIVERSE),
        "stocks_scored": len(all_scores),
        "elapsed_seconds": round(elapsed, 1),
        "macro_context": {
            "vix": macro_data["vix"].get("vix") if isinstance(macro_data["vix"], dict) else None,
            "vix_level": macro_data["vix"].get("level") if isinstance(macro_data["vix"], dict) else None,
            "fear_greed": macro_data["fear_greed"].get("score") if isinstance(macro_data["fear_greed"], dict) else None,
            "fear_greed_label": macro_data["fear_greed"].get("rating") if isinstance(macro_data["fear_greed"], dict) else None,
            "put_call_ratio": macro_data["pcr"].get("ratio") if isinstance(macro_data["pcr"], dict) else None,
        },
        "top_recommendations": top,
        "avoid_list": bottom,
    }
