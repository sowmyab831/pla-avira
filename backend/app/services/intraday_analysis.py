"""
Intraday Trading Analysis — Options Trader Toolkit

Provides:
- Real-time price fetch via yfinance
- Classic + Woodie + Camarilla pivot points
- ATR-based buy/sell/stop targets
- Algorithmic chart pattern detection
- Expected daily move ranges
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Pivot Point Calculators ────────────────────────────────────────────────

def _classic_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    p = (high + low + close) / 3
    r = high - low
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - low, 2),
        "r2": round(p + r, 2),
        "r3": round(high + 2 * (p - low), 2),
        "s1": round(2 * p - high, 2),
        "s2": round(p - r, 2),
        "s3": round(low - 2 * (high - p), 2),
    }


def _woodie_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    p = (high + low + 2 * close) / 4
    r = high - low
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - low, 2),
        "r2": round(p + r, 2),
        "s1": round(2 * p - high, 2),
        "s2": round(p - r, 2),
    }


def _camarilla_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    r = high - low
    return {
        "r4": round(close + r * 1.1 / 2, 2),
        "r3": round(close + r * 1.1 / 4, 2),
        "r2": round(close + r * 1.1 / 6, 2),
        "r1": round(close + r * 1.1 / 12, 2),
        "s1": round(close - r * 1.1 / 12, 2),
        "s2": round(close - r * 1.1 / 6, 2),
        "s3": round(close - r * 1.1 / 4, 2),
        "s4": round(close - r * 1.1 / 2, 2),
    }


# ── ATR Calculation ────────────────────────────────────────────────────────

def _calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    if len(highs) < 2:
        return 0.0
    true_ranges = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)
    if not true_ranges:
        return 0.0
    relevant = true_ranges[-period:]
    return round(float(np.mean(relevant)), 4)


# ── Chart Pattern Detection ────────────────────────────────────────────────

def _detect_double_top(highs: List[float], closes: List[float], tolerance: float = 0.015) -> Optional[Dict]:
    if len(highs) < 15:
        return None
    recent = highs[-30:]
    peaks = []
    for i in range(2, len(recent) - 2):
        if recent[i] > recent[i-1] and recent[i] > recent[i-2] and recent[i] > recent[i+1] and recent[i] > recent[i+2]:
            peaks.append((i, recent[i]))
    if len(peaks) < 2:
        return None
    for i in range(len(peaks) - 1):
        for j in range(i + 1, len(peaks)):
            idx1, p1 = peaks[i]
            idx2, p2 = peaks[j]
            if j - i >= 3 and abs(p1 - p2) / max(p1, p2) <= tolerance:
                valley = min(recent[idx1:idx2])
                neck = valley
                current = closes[-1]
                if current < neck * 1.01:
                    return {
                        "pattern": "double_top",
                        "signal": "bearish",
                        "peak1": round(p1, 2),
                        "peak2": round(p2, 2),
                        "neckline": round(neck, 2),
                        "target": round(neck - (p1 - neck), 2),
                        "confidence": 0.75,
                    }
    return None


def _detect_double_bottom(lows: List[float], closes: List[float], tolerance: float = 0.015) -> Optional[Dict]:
    if len(lows) < 15:
        return None
    recent = lows[-30:]
    troughs = []
    for i in range(2, len(recent) - 2):
        if recent[i] < recent[i-1] and recent[i] < recent[i-2] and recent[i] < recent[i+1] and recent[i] < recent[i+2]:
            troughs.append((i, recent[i]))
    if len(troughs) < 2:
        return None
    for i in range(len(troughs) - 1):
        for j in range(i + 1, len(troughs)):
            idx1, t1 = troughs[i]
            idx2, t2 = troughs[j]
            if j - i >= 3 and abs(t1 - t2) / max(t1, t2) <= tolerance:
                peak = max(lows[idx1:idx2])
                neck = peak
                current = closes[-1]
                if current > neck * 0.99:
                    return {
                        "pattern": "double_bottom",
                        "signal": "bullish",
                        "trough1": round(t1, 2),
                        "trough2": round(t2, 2),
                        "neckline": round(neck, 2),
                        "target": round(neck + (neck - t1), 2),
                        "confidence": 0.75,
                    }
    return None


def _detect_higher_highs_lows(highs: List[float], lows: List[float]) -> Optional[Dict]:
    """Detect trend direction using first-half vs second-half median comparison."""
    if len(highs) < 8:
        return None
    n = min(12, len(highs))
    h = highs[-n:]
    l = lows[-n:]
    half = n // 2
    # Compare second half median vs first half median
    h_first = float(np.median(h[:half]))
    h_second = float(np.median(h[half:]))
    l_first = float(np.median(l[:half]))
    l_second = float(np.median(l[half:]))
    # At least 0.5% move required
    threshold = 0.005
    h_up = h_second > h_first * (1 + threshold)
    l_up = l_second > l_first * (1 + threshold)
    h_dn = h_second < h_first * (1 - threshold)
    l_dn = l_second < l_first * (1 - threshold)
    if h_up and l_up:
        pct = round((h_second - h_first) / h_first * 100, 1)
        return {"pattern": "higher_highs_lows", "signal": "bullish", "confidence": 0.70,
                "description": f"Uptrend confirmed: price structure rising +{pct}% over past {n} sessions"}
    if h_dn and l_dn:
        pct = round((h_first - h_second) / h_first * 100, 1)
        return {"pattern": "lower_highs_lows", "signal": "bearish", "confidence": 0.70,
                "description": f"Downtrend confirmed: price structure falling -{pct}% over past {n} sessions"}
    return None


def _detect_flag_pennant(closes: List[float], volumes: List[float]) -> Optional[Dict]:
    if len(closes) < 20:
        return None
    pole_period = 5
    flag_period = min(10, len(closes) - pole_period)
    if flag_period < 5:
        return None
    pole = closes[-(pole_period + flag_period):-flag_period]
    flag = closes[-flag_period:]
    pole_move = (pole[-1] - pole[0]) / pole[0] * 100
    flag_move = (flag[-1] - flag[0]) / flag[0] * 100
    if abs(pole_move) > 5 and abs(flag_move) < abs(pole_move) * 0.5:
        signal = "bullish" if pole_move > 0 else "bearish"
        return {
            "pattern": "flag_pennant",
            "signal": signal,
            "pole_move_pct": round(pole_move, 2),
            "flag_move_pct": round(flag_move, 2),
            "confidence": 0.65,
            "description": f"{'Bull' if signal == 'bullish' else 'Bear'} flag: {abs(pole_move):.1f}% move with {abs(flag_move):.1f}% consolidation",
        }
    return None


def _detect_rsi_divergence(closes: List[float], rsi_values: List[float]) -> Optional[Dict]:
    if len(closes) < 14 or len(rsi_values) < 14:
        return None
    n = min(20, len(closes), len(rsi_values))
    c = closes[-n:]
    r = rsi_values[-n:]
    price_higher = c[-1] > c[-n // 2]
    rsi_lower = r[-1] < r[-n // 2]
    price_lower = c[-1] < c[-n // 2]
    rsi_higher = r[-1] > r[-n // 2]
    if price_higher and rsi_lower and r[-1] > 50:
        return {"pattern": "bearish_divergence", "signal": "bearish", "confidence": 0.70,
                "description": "Price making higher highs but RSI making lower highs — momentum weakening"}
    if price_lower and rsi_higher and r[-1] < 50:
        return {"pattern": "bullish_divergence", "signal": "bullish", "confidence": 0.70,
                "description": "Price making lower lows but RSI making higher lows — potential reversal ahead"}
    return None


def _detect_macd_signal(closes: List[float]) -> Optional[Dict]:
    if len(closes) < 26:
        return None
    c = np.array(closes)
    ema12 = float(np.mean(c[-12:]))  # simplified
    ema26 = float(np.mean(c[-26:]))
    macd_line = ema12 - ema26
    signal = np.mean([np.mean(closes[-(26+i):-(14+i)] if i > 0 else closes[-26:-14]) for i in range(9)])
    hist = macd_line - float(signal)
    if hist > 0 and macd_line > 0:
        return {"pattern": "macd_bullish_crossover", "signal": "bullish", "confidence": 0.65,
                "macd": round(macd_line, 4), "histogram": round(hist, 4),
                "description": "MACD above signal line with positive histogram — bullish momentum"}
    if hist < 0 and macd_line < 0:
        return {"pattern": "macd_bearish_crossover", "signal": "bearish", "confidence": 0.65,
                "macd": round(macd_line, 4), "histogram": round(hist, 4),
                "description": "MACD below signal line with negative histogram — bearish momentum"}
    return None


def _detect_cup_handle(closes: List[float]) -> Optional[Dict]:
    if len(closes) < 30:
        return None
    c = closes[-40:] if len(closes) >= 40 else closes
    n = len(c)
    left_high = max(c[:n//4])
    cup_low = min(c[n//4:3*n//4])
    right_high = max(c[3*n//4:n-n//10]) if n > n//10 else 0
    handle_low = min(c[n - n//10:])
    depth = (left_high - cup_low) / left_high if left_high > 0 else 0
    symmetry = abs(left_high - right_high) / left_high if left_high > 0 else 1
    if 0.1 <= depth <= 0.5 and symmetry < 0.05 and handle_low > cup_low:
        return {
            "pattern": "cup_and_handle",
            "signal": "bullish",
            "confidence": 0.60,
            "cup_depth_pct": round(depth * 100, 1),
            "target": round(right_high + (right_high - cup_low), 2),
            "description": f"Cup & Handle: {depth*100:.1f}% cup depth — breakout above ${right_high:.2f} targets ${right_high+(right_high-cup_low):.2f}",
        }
    return None


def _calculate_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = np.mean(gains) if gains else 0
    avg_loss = np.mean(losses) if losses else 1e-9
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


# ── Main Analysis Function ─────────────────────────────────────────────────

def get_intraday_analysis(symbol: str) -> Dict[str, Any]:
    """
    Full intraday analysis for options traders.
    Returns real-time price, pivot levels, pattern detection, and trade targets.
    """
    try:
        ticker = yf.Ticker(symbol)

        # Get today's intraday data (1m intervals, 1d range)
        intraday = ticker.history(period="1d", interval="1m")
        # Get last 20 days for pattern detection and ATR
        daily = ticker.history(period="20d", interval="1d")
        # Get previous day OHLC for pivot points
        prev_day = ticker.history(period="2d", interval="1d")

        if daily.empty or len(daily) < 2:
            return {"error": f"No data for {symbol}", "symbol": symbol}

        # Current real-time price
        current_price = float(intraday["Close"].iloc[-1]) if not intraday.empty else float(daily["Close"].iloc[-1])
        today_open = float(intraday["Open"].iloc[0]) if not intraday.empty else float(daily["Open"].iloc[-1])
        today_high = float(intraday["High"].max()) if not intraday.empty else float(daily["High"].iloc[-1])
        today_low = float(intraday["Low"].min()) if not intraday.empty else float(daily["Low"].iloc[-1])

        # Previous day OHLC for pivot points
        prev = prev_day.iloc[-2] if len(prev_day) >= 2 else daily.iloc[-1]
        prev_high = float(prev["High"])
        prev_low = float(prev["Low"])
        prev_close = float(prev["Close"])

        # Lists for indicator calculation
        daily_closes = [float(x) for x in daily["Close"].tolist()]
        daily_highs = [float(x) for x in daily["High"].tolist()]
        daily_lows = [float(x) for x in daily["Low"].tolist()]
        daily_volumes = [float(x) for x in daily["Volume"].tolist()]

        # --- Pivot Points ---
        classic = _classic_pivots(prev_high, prev_low, prev_close)
        woodie = _woodie_pivots(prev_high, prev_low, prev_close)
        camarilla = _camarilla_pivots(prev_high, prev_low, prev_close)

        # --- ATR ---
        atr = _calculate_atr(daily_highs, daily_lows, daily_closes, 14)
        atr_pct = round(atr / current_price * 100, 2) if current_price else 0

        # --- RSI ---
        rsi = _calculate_rsi(daily_closes, 14)

        # --- Pattern Detection ---
        rsi_series = [_calculate_rsi(daily_closes[:i+14], 14) for i in range(len(daily_closes) - 13)]
        patterns_found = []
        for detector, args in [
            (_detect_double_top, (daily_highs, daily_closes)),
            (_detect_double_bottom, (daily_lows, daily_closes)),
            (_detect_higher_highs_lows, (daily_highs, daily_lows)),
            (_detect_flag_pennant, (daily_closes, daily_volumes)),
            (_detect_rsi_divergence, (daily_closes, rsi_series)),
            (_detect_macd_signal, (daily_closes,)),
            (_detect_cup_handle, (daily_closes,)),
        ]:
            try:
                result = detector(*args)
                if result:
                    patterns_found.append(result)
            except Exception:
                pass

        # --- Options Trade Targets ---
        # Find nearest resistance above and support below current price
        all_resistance = [v for v in [classic["r1"], classic["r2"], camarilla["r3"]] if v > current_price]
        all_support = [v for v in [classic["s1"], classic["s2"], camarilla["s3"]] if v < current_price]
        nearest_resistance = min(all_resistance) if all_resistance else round(current_price * 1.02, 2)
        nearest_support = max(all_support) if all_support else round(current_price * 0.98, 2)

        # Expected daily move (1 ATR ≈ ~68% probability range)
        expected_move = round(atr * 0.7, 2)  # typical intraday is ~70% of ATR

        # Bull call targets — enter on breakout above resistance
        call_entry = round(nearest_resistance * 1.003, 2)  # breakout: just above resistance
        call_stop = round(nearest_resistance * 0.997, 2)   # invalidation: if resistance holds
        # Targets are next resistance levels above entry
        r_levels_above = sorted([v for v in [classic["r1"], classic["r2"], classic["r3"]] if v > call_entry])
        call_target1 = round(r_levels_above[0], 2) if r_levels_above else round(call_entry + atr, 2)
        call_target2 = round(r_levels_above[1], 2) if len(r_levels_above) > 1 else round(call_entry + atr * 2, 2)
        call_risk = call_entry - call_stop
        call_rr = round((call_target1 - call_entry) / call_risk, 2) if call_risk > 0 else 0

        # Bear put targets — enter on breakdown below support
        put_entry = round(nearest_support * 0.997, 2)  # breakdown: just below support
        put_stop = round(nearest_support * 1.003, 2)   # invalidation: if support holds
        # Targets are next support levels BELOW entry
        s_levels_below = sorted([v for v in [classic["s1"], classic["s2"], classic["s3"]] if v < put_entry], reverse=True)
        put_target1 = round(s_levels_below[0], 2) if s_levels_below else round(put_entry - atr, 2)
        put_target2 = round(s_levels_below[1], 2) if len(s_levels_below) > 1 else round(put_entry - atr * 2, 2)
        put_risk = put_stop - put_entry
        put_rr = round((put_entry - put_target1) / put_risk, 2) if put_risk > 0 else 0

        # Overall bias based on price vs pivot
        bias = "bullish" if current_price > classic["pivot"] else "bearish"
        if rsi > 70:
            bias = "overbought_caution"
        elif rsi < 30:
            bias = "oversold_opportunity"

        # Day change
        prev_close_val = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else current_price
        day_change = round(current_price - prev_close_val, 2)
        day_change_pct = round((day_change / prev_close_val) * 100, 2) if prev_close_val else 0

        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "success": True,

            "price": {
                "current": round(current_price, 2),
                "open": round(today_open, 2),
                "high": round(today_high, 2),
                "low": round(today_low, 2),
                "prev_close": round(prev_close_val, 2),
                "day_change": day_change,
                "day_change_pct": day_change_pct,
            },

            "indicators": {
                "rsi": rsi,
                "atr": round(atr, 2),
                "atr_pct": atr_pct,
                "expected_daily_move": expected_move,
                "bias": bias,
            },

            "pivot_points": {
                "classic": classic,
                "woodie": woodie,
                "camarilla": camarilla,
            },

            "trade_targets": {
                "bias": bias,
                "call_trade": {
                    "type": "CALL (Bull)",
                    "entry": call_entry,
                    "stop_loss": call_stop,
                    "target1": call_target1,
                    "target2": call_target2,
                    "risk_reward": call_rr,
                    "note": f"Enter call when price breaks above ${nearest_resistance} with volume",
                },
                "put_trade": {
                    "type": "PUT (Bear)",
                    "entry": put_entry,
                    "stop_loss": put_stop,
                    "target1": put_target1,
                    "target2": put_target2,
                    "risk_reward": put_rr,
                    "note": f"Enter put when price breaks below ${nearest_support} with volume",
                },
                "expected_range_today": {
                    "high": round(current_price + expected_move, 2),
                    "low": round(current_price - expected_move, 2),
                    "range_pct": atr_pct,
                },
            },

            "patterns": patterns_found,
            "pattern_count": len(patterns_found),
        }

    except Exception as e:
        logger.error(f"Intraday analysis error for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol, "success": False}
