"""
Deep Stock Analysis Service

Combines all signal sources into a single comprehensive analysis:
- Elliott Wave patterns + Fibonacci levels
- Technical indicators (RSI, MACD, Bollinger, S/R)
- Market sentiment (Reddit, Yahoo News, Fear/Greed)
- Institutional tracking (13F, insider trades, analyst ratings)
- Weekly posture + next-week outlook
- AI-powered synthesis via DeepSeek-R1:32B

This is the most powerful analysis endpoint in the system.
"""

import asyncio
import hashlib
import httpx
import json as _json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.services.elliott_wave import analyze_elliott_wave
from app.services.market_sentiment import get_market_sentiment
from app.services.institutional_tracker import get_institutional_analysis
from app.utils.technical_indicators import get_full_technical_analysis
from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)

# In-memory cache with TTL (fallback if Redis unavailable)
_cache: Dict[str, Dict] = {}
CACHE_TTL = 300  # 5 minutes


def _cache_get(key: str) -> Optional[Dict]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: Dict):
    _cache[key] = {"data": data, "ts": time.time()}
    # Evict old entries (keep max 50)
    if len(_cache) > 50:
        oldest = sorted(_cache, key=lambda k: _cache[k]["ts"])[:10]
        for k in oldest:
            del _cache[k]


async def _fetch_price_history(symbol: str, period: str = "6mo") -> Dict:
    """Fetch OHLCV data from Yahoo Finance v8 API."""
    interval = "1d"
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={period}&interval={interval}"
            resp = await client.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return {}

            data = resp.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            timestamps = result.get("timestamp", [])
            quotes = result.get("indicators", {}).get("quote", [{}])[0]

            closes = quotes.get("close", [])
            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            volumes = quotes.get("volume", [])

            # Filter out None values
            valid = []
            for i in range(len(closes)):
                if closes[i] is not None:
                    valid.append({
                        "date": datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d") if i < len(timestamps) else "",
                        "open": opens[i],
                        "high": highs[i],
                        "low": lows[i],
                        "close": closes[i],
                        "volume": volumes[i] if i < len(volumes) else 0,
                    })

            return {
                "symbol": meta.get("symbol", symbol),
                "currency": meta.get("currency", "USD"),
                "exchange": meta.get("exchangeName", ""),
                "current_price": meta.get("regularMarketPrice", closes[-1] if closes else 0),
                "previous_close": meta.get("previousClose", 0),
                "data_points": len(valid),
                "candles": valid,
                "closes": [v["close"] for v in valid],
                "highs": [v["high"] for v in valid],
                "lows": [v["low"] for v in valid],
                "volumes": [v["volume"] for v in valid],
            }
        except Exception as e:
            logger.error(f"Price history error for {symbol}: {e}")
            return {}


def _weekly_posture(closes: List[float], technicals: Dict) -> Dict:
    """Determine weekly market posture and next-week outlook."""
    if len(closes) < 10:
        return {"posture": "insufficient_data"}

    # Last 5 trading days vs previous 5
    current_week = closes[-5:]
    prev_week = closes[-10:-5]

    week_change = ((current_week[-1] - prev_week[-1]) / prev_week[-1]) * 100
    week_high = max(current_week)
    week_low = min(current_week)
    week_range = ((week_high - week_low) / week_low) * 100

    # Momentum: are we closing near the high or low of the week?
    week_position = (current_week[-1] - week_low) / (week_high - week_low) if week_high != week_low else 0.5

    # RSI from technicals (may be float or dict)
    rsi_raw = technicals.get("rsi", 50)
    rsi = rsi_raw.get("value", 50) if isinstance(rsi_raw, dict) else float(rsi_raw)

    # Determine posture
    if week_change > 2 and week_position > 0.7 and rsi < 70:
        posture = "strong_bullish"
        outlook = "Momentum continues upward. Look for pullbacks to add."
    elif week_change > 0.5 and week_position > 0.5:
        posture = "bullish"
        outlook = "Uptrend intact. Watch for resistance at weekly high."
    elif week_change < -2 and week_position < 0.3 and rsi > 30:
        posture = "strong_bearish"
        outlook = "Heavy selling pressure. Wait for support confirmation before buying."
    elif week_change < -0.5 and week_position < 0.5:
        posture = "bearish"
        outlook = "Downtrend continuing. Potential bounce at support levels."
    elif week_range > 5:
        posture = "volatile"
        outlook = "High volatility — expect continued swings. Reduce position size."
    else:
        posture = "neutral"
        outlook = "Consolidation range. Breakout direction will define next move."

    return {
        "posture": posture,
        "week_change_pct": round(week_change, 2),
        "week_high": round(week_high, 2),
        "week_low": round(week_low, 2),
        "week_range_pct": round(week_range, 2),
        "close_position": round(week_position, 2),  # 0=at low, 1=at high
        "next_week_outlook": outlook,
    }


async def _ai_synthesis(
    symbol: str,
    price_data: Dict,
    elliott: Dict,
    technicals: Dict,
    sentiment: Dict,
    institutional: Dict,
    weekly: Dict,
) -> str:
    """Synthesize all signals into actionable advice via the deep/finance model."""
    try:

        # Extract technicals safely (rsi can be float or dict)
        rsi_raw = technicals.get('rsi', 50)
        rsi_val = rsi_raw.get('value', 50) if isinstance(rsi_raw, dict) else rsi_raw
        rsi_sig = rsi_raw.get('signal', '') if isinstance(rsi_raw, dict) else ('oversold' if rsi_val < 30 else 'overbought' if rsi_val > 70 else 'neutral')
        macd_sig = technicals.get('macd', {}).get('trend', technicals.get('macd', {}).get('signal', 'N/A')) if isinstance(technicals.get('macd'), dict) else 'N/A'
        bb = technicals.get('bollinger_bands', technicals.get('bollinger', {}))
        bb_sig = bb.get('position', bb.get('signal', 'N/A')) if isinstance(bb, dict) else 'N/A'

        prompt = f"""You are an expert quantitative analyst. Analyze {symbol} using these signals and give a concise, actionable recommendation.

PRICE: ${price_data.get('current_price', 'N/A')} | Week: {weekly.get('week_change_pct', 0)}%

ELLIOTT WAVE: {elliott.get('trend', 'N/A')} trend
- Impulse pattern: {elliott.get('impulse_wave', {}).get('type', 'none detected') if isinstance(elliott.get('impulse_wave'), dict) else 'none detected'}
- Wave position: {elliott.get('wave_position', {}).get('position', 'N/A') if isinstance(elliott.get('wave_position'), dict) else 'N/A'}
- Fibonacci support: {list(elliott.get('fibonacci', {}).get('support_levels', {}).items())[:3] if isinstance(elliott.get('fibonacci'), dict) else 'N/A'}

TECHNICALS:
- RSI: {rsi_val} ({rsi_sig})
- MACD: {macd_sig}
- Bollinger: {bb_sig}
- Overall: {technicals.get('overall_signal', 'N/A')}

SENTIMENT: {sentiment.get('overall_signal', 'N/A')} (score: {sentiment.get('composite_score', 0)})
- Reddit: {sentiment.get('sources', {}).get('reddit', {}).get('signal', 'N/A') if isinstance(sentiment.get('sources', {}).get('reddit'), dict) else 'N/A'}
- News: {sentiment.get('sources', {}).get('yahoo_finance', {}).get('signal', 'N/A') if isinstance(sentiment.get('sources', {}).get('yahoo_finance'), dict) else 'N/A'}
- Fear/Greed: {sentiment.get('fear_greed_index', {}).get('label', 'N/A') if isinstance(sentiment.get('fear_greed_index'), dict) else 'N/A'}

INSTITUTIONAL:
- Analyst consensus: {institutional.get('analyst_ratings', {}).get('recommendation', 'N/A') if isinstance(institutional.get('analyst_ratings'), dict) else 'N/A'}
- Target price: ${institutional.get('analyst_ratings', {}).get('target_mean', 'N/A') if isinstance(institutional.get('analyst_ratings'), dict) else 'N/A'}
- Upside: {institutional.get('upside_potential_pct', 'N/A')}%
- Insider activity: {institutional.get('accumulation_signals', {}).get('details', ['None']) if isinstance(institutional.get('accumulation_signals'), dict) else 'N/A'}

WEEKLY POSTURE: {weekly.get('posture', 'N/A')}

Provide:
1. VERDICT (1 line): BUY / HOLD / SELL with conviction level (high/medium/low)
2. KEY SIGNALS (3 bullets): Most important data points driving the verdict
3. RISK (1 line): Primary risk to watch
4. NEXT WEEK (1 line): What to expect
5. PRICE TARGETS: Entry, stop-loss, take-profit levels

Be direct. No disclaimers. Think like a hedge fund analyst."""

        response = await llm_generate(
            prompt,
            task="deep",
            system="You are a senior quantitative analyst at a top hedge fund. Be concise and decisive.",
            timeout=120,
            temperature=0.3,
            max_tokens=1200,
        )
        return response or "AI synthesis unavailable: empty response"
    except Exception as e:
        logger.error(f"AI synthesis error: {e}")
        return f"AI synthesis unavailable: {e}"


async def get_deep_analysis(symbol: str, skip_ai: bool = False) -> Dict[str, Any]:
    """
    Run comprehensive deep analysis on a stock.

    Combines: price history, Elliott Wave, technicals, sentiment,
    institutional data, weekly posture, and AI synthesis.

    Results are cached for 5 minutes to avoid redundant computation.
    """
    cache_key = f"deep:{symbol}:{1 if skip_ai else 0}"
    cached = _cache_get(cache_key)
    if cached:
        cached["from_cache"] = True
        return cached

    start = time.time()
    timings = {}

    # Phase 1: Fetch price history (needed for Elliott Wave + technicals)
    t0 = time.time()
    price_data = await _fetch_price_history(symbol, "6mo")
    timings["price_fetch"] = round(time.time() - t0, 2)

    if not price_data or not price_data.get("closes"):
        return {"error": f"Could not fetch price data for {symbol}", "symbol": symbol}

    closes = price_data["closes"]
    highs = price_data["highs"]
    lows = price_data["lows"]
    volumes = price_data["volumes"]

    # Phase 2: Run ALL analyses in parallel (including technicals)
    t0 = time.time()
    elliott_task = asyncio.to_thread(analyze_elliott_wave, closes)
    sentiment_task = get_market_sentiment(symbol)
    institutional_task = get_institutional_analysis(symbol)
    technicals_task = asyncio.to_thread(
        get_full_technical_analysis, closes, highs, lows, volumes,
    )

    elliott, sentiment, institutional, technicals = await asyncio.gather(
        elliott_task, sentiment_task, institutional_task, technicals_task,
        return_exceptions=True,
    )
    timings["parallel_analysis"] = round(time.time() - t0, 2)

    if isinstance(elliott, Exception):
        logger.warning(f"Elliott wave error: {elliott}")
        elliott = {"error": str(elliott)}
    if isinstance(sentiment, Exception):
        logger.warning(f"Sentiment error: {sentiment}")
        sentiment = {"error": str(sentiment)}
    if isinstance(institutional, Exception):
        logger.warning(f"Institutional error: {institutional}")
        institutional = {"error": str(institutional)}
    if isinstance(technicals, Exception):
        logger.warning(f"Technicals error: {technicals}")
        technicals = {"error": str(technicals)}

    # Phase 3: Weekly posture (fast, ~0ms)
    weekly = _weekly_posture(closes, technicals if isinstance(technicals, dict) else {})

    # Phase 4: AI synthesis (optional — skip for fast mode)
    ai_summary = ""
    if not skip_ai:
        t0 = time.time()
        ai_summary = await _ai_synthesis(
            symbol, price_data, elliott, technicals, sentiment, institutional, weekly,
        )
        timings["ai_synthesis"] = round(time.time() - t0, 2)

    elapsed = round(time.time() - start, 2)
    timings["total"] = elapsed

    result = {
        "success": True,
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "processing_time_seconds": elapsed,
        "timings": timings,
        "current_price": price_data.get("current_price"),
        "previous_close": price_data.get("previous_close"),

        "ai_verdict": ai_summary,

        "weekly_posture": weekly,
        "elliott_wave": elliott,
        "technical_indicators": technicals,
        "market_sentiment": sentiment,
        "institutional_analysis": institutional,

        "price_targets": elliott.get("price_targets", {}) if isinstance(elliott, dict) else {},
        "fibonacci_levels": elliott.get("fibonacci", {}) if isinstance(elliott, dict) else {},
        "moving_averages": elliott.get("moving_averages", {}) if isinstance(elliott, dict) else {},
    }

    _cache_set(cache_key, result)
    logger.info(f"Deep analysis {symbol}: {elapsed}s — {timings}")
    return result
