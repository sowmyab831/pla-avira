"""
Elliott Wave Pattern Detector + Advanced Chart Analysis

Uses scipy for peak/trough detection on OHLCV data.
Classifies impulse (1-5) and corrective (A-B-C) waves.
Predicts next wave direction and price targets.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def _find_pivots(prices: List[float], window: int = 5) -> Tuple[List[int], List[int]]:
    """Find local highs and lows using rolling window comparison."""
    n = len(prices)
    if n < window * 2 + 1:
        return [], []

    highs, lows = [], []
    for i in range(window, n - window):
        is_high = all(prices[i] >= prices[i - j] and prices[i] >= prices[i + j] for j in range(1, window + 1))
        is_low = all(prices[i] <= prices[i - j] and prices[i] <= prices[i + j] for j in range(1, window + 1))
        if is_high:
            highs.append(i)
        if is_low:
            lows.append(i)
    return highs, lows


def _merge_pivots(prices: List[float], highs: List[int], lows: List[int]) -> List[Dict]:
    """Merge highs and lows into alternating pivot sequence."""
    pivots = []
    for i in highs:
        pivots.append({"index": i, "price": prices[i], "type": "high"})
    for i in lows:
        pivots.append({"index": i, "price": prices[i], "type": "low"})

    pivots.sort(key=lambda x: x["index"])

    # Remove consecutive same-type pivots (keep the more extreme one)
    filtered = []
    for p in pivots:
        if not filtered or filtered[-1]["type"] != p["type"]:
            filtered.append(p)
        else:
            if p["type"] == "high" and p["price"] > filtered[-1]["price"]:
                filtered[-1] = p
            elif p["type"] == "low" and p["price"] < filtered[-1]["price"]:
                filtered[-1] = p
    return filtered


def _fibonacci_ratios() -> Dict[str, float]:
    return {
        "0.236": 0.236, "0.382": 0.382, "0.500": 0.500,
        "0.618": 0.618, "0.786": 0.786, "1.000": 1.000,
        "1.272": 1.272, "1.618": 1.618, "2.618": 2.618,
    }


def _check_impulse_wave(pivots: List[Dict]) -> Optional[Dict]:
    """Check if pivots form a valid 5-wave impulse pattern.

    Rules:
    - Wave 2 cannot retrace more than 100% of Wave 1
    - Wave 3 cannot be the shortest impulse wave
    - Wave 4 cannot overlap Wave 1's territory
    """
    if len(pivots) < 6:
        return None

    # Try bullish impulse: low-high-low-high-low-high (waves 1-5)
    for i in range(len(pivots) - 5):
        pts = pivots[i:i + 6]
        if pts[0]["type"] != "low":
            continue

        p0, p1, p2, p3, p4, p5 = [p["price"] for p in pts]

        # Basic structure: alternating up-down-up-down-up
        if not (p1 > p0 and p2 < p1 and p3 > p2 and p4 < p3 and p5 > p4):
            continue

        w1 = p1 - p0
        w2 = p1 - p2
        w3 = p3 - p2
        w4 = p3 - p4
        w5 = p5 - p4

        # Rule 1: Wave 2 retracement < 100% of Wave 1
        if w2 >= w1:
            continue

        # Rule 2: Wave 3 is not the shortest
        if w3 < w1 and w3 < w5:
            continue

        # Rule 3: Wave 4 doesn't overlap Wave 1 (p4 > p1 would be overlap)
        if p4 < p1:
            continue

        w2_retrace = w2 / w1 if w1 > 0 else 0
        w4_retrace = w4 / w3 if w3 > 0 else 0
        w3_extension = w3 / w1 if w1 > 0 else 0

        return {
            "type": "bullish_impulse",
            "waves": {
                "wave_1": {"start": p0, "end": p1, "magnitude": w1},
                "wave_2": {"start": p1, "end": p2, "retracement": round(w2_retrace, 3)},
                "wave_3": {"start": p2, "end": p3, "extension": round(w3_extension, 3)},
                "wave_4": {"start": p3, "end": p4, "retracement": round(w4_retrace, 3)},
                "wave_5": {"start": p4, "end": p5, "magnitude": w5},
            },
            "start_index": pts[0]["index"],
            "end_index": pts[5]["index"],
            "confidence": _impulse_confidence(w2_retrace, w3_extension, w4_retrace),
        }

    # Try bearish impulse: high-low-high-low-high-low
    for i in range(len(pivots) - 5):
        pts = pivots[i:i + 6]
        if pts[0]["type"] != "high":
            continue

        p0, p1, p2, p3, p4, p5 = [p["price"] for p in pts]

        if not (p1 < p0 and p2 > p1 and p3 < p2 and p4 > p3 and p5 < p4):
            continue

        w1 = p0 - p1
        w2 = p2 - p1
        w3 = p2 - p3
        w4 = p4 - p3
        w5 = p4 - p5

        if w2 >= w1:
            continue
        if w3 < w1 and w3 < w5:
            continue
        if p4 > p1:
            continue

        w2_retrace = w2 / w1 if w1 > 0 else 0
        w4_retrace = w4 / w3 if w3 > 0 else 0
        w3_extension = w3 / w1 if w1 > 0 else 0

        return {
            "type": "bearish_impulse",
            "waves": {
                "wave_1": {"start": p0, "end": p1, "magnitude": w1},
                "wave_2": {"start": p1, "end": p2, "retracement": round(w2_retrace, 3)},
                "wave_3": {"start": p2, "end": p3, "extension": round(w3_extension, 3)},
                "wave_4": {"start": p3, "end": p4, "retracement": round(w4_retrace, 3)},
                "wave_5": {"start": p4, "end": p5, "magnitude": w5},
            },
            "start_index": pts[0]["index"],
            "end_index": pts[5]["index"],
            "confidence": _impulse_confidence(w2_retrace, w3_extension, w4_retrace),
        }

    return None


def _impulse_confidence(w2_retrace: float, w3_ext: float, w4_retrace: float) -> float:
    """Score impulse wave quality. Higher = more textbook."""
    score = 50.0
    # Ideal Wave 2 retracement: 0.382-0.618
    if 0.35 <= w2_retrace <= 0.65:
        score += 15
    elif 0.2 <= w2_retrace <= 0.786:
        score += 8

    # Ideal Wave 3 extension: 1.618+
    if w3_ext >= 1.618:
        score += 20
    elif w3_ext >= 1.272:
        score += 12
    elif w3_ext >= 1.0:
        score += 5

    # Ideal Wave 4 retracement: 0.236-0.382
    if 0.2 <= w4_retrace <= 0.42:
        score += 15
    elif 0.15 <= w4_retrace <= 0.618:
        score += 8

    return min(round(score, 1), 100.0)


def _check_corrective(pivots: List[Dict]) -> Optional[Dict]:
    """Check for A-B-C corrective pattern after an impulse."""
    if len(pivots) < 4:
        return None

    # Look for zigzag correction (3 pivots after impulse)
    for i in range(len(pivots) - 3):
        pts = pivots[i:i + 4]
        p0, p1, p2, p3 = [p["price"] for p in pts]

        # Bearish correction: high-low-high-low
        if pts[0]["type"] == "high" and p1 < p0 and p2 > p1 and p3 < p2:
            a_mag = p0 - p1
            b_retrace = (p2 - p1) / a_mag if a_mag > 0 else 0
            c_mag = p2 - p3

            if 0.3 <= b_retrace <= 0.786:
                return {
                    "type": "bearish_correction",
                    "pattern": "zigzag" if c_mag >= a_mag * 0.618 else "flat",
                    "wave_a": {"magnitude": a_mag},
                    "wave_b": {"retracement": round(b_retrace, 3)},
                    "wave_c": {"magnitude": c_mag},
                    "start_index": pts[0]["index"],
                    "end_index": pts[3]["index"],
                }

        # Bullish correction: low-high-low-high
        if pts[0]["type"] == "low" and p1 > p0 and p2 < p1 and p3 > p2:
            a_mag = p1 - p0
            b_retrace = (p1 - p2) / a_mag if a_mag > 0 else 0
            c_mag = p3 - p2

            if 0.3 <= b_retrace <= 0.786:
                return {
                    "type": "bullish_correction",
                    "pattern": "zigzag" if c_mag >= a_mag * 0.618 else "flat",
                    "wave_a": {"magnitude": a_mag},
                    "wave_b": {"retracement": round(b_retrace, 3)},
                    "wave_c": {"magnitude": c_mag},
                    "start_index": pts[0]["index"],
                    "end_index": pts[3]["index"],
                }

    return None


def _fibonacci_levels(high: float, low: float, direction: str = "up") -> Dict[str, float]:
    """Calculate Fibonacci retracement/extension levels."""
    diff = high - low
    ratios = _fibonacci_ratios()

    if direction == "up":
        return {k: round(low + diff * v, 2) for k, v in ratios.items()}
    else:
        return {k: round(high - diff * v, 2) for k, v in ratios.items()}


def _current_wave_position(prices: List[float], pivots: List[Dict]) -> Dict:
    """Determine where we are in the current wave cycle."""
    if not pivots or len(pivots) < 2:
        return {"position": "insufficient_data", "direction": "neutral"}

    last = pivots[-1]
    prev = pivots[-2]
    current = prices[-1]

    if last["type"] == "low":
        # Currently in an upswing from the last low
        move_pct = ((current - last["price"]) / last["price"]) * 100
        return {
            "position": "upswing",
            "from_pivot": last["price"],
            "current": current,
            "move_pct": round(move_pct, 2),
            "direction": "bullish",
        }
    else:
        move_pct = ((last["price"] - current) / last["price"]) * 100
        return {
            "position": "downswing",
            "from_pivot": last["price"],
            "current": current,
            "move_pct": round(move_pct, 2),
            "direction": "bearish",
        }


def analyze_elliott_wave(
    prices: List[float],
    dates: Optional[List[str]] = None,
    window: int = 5,
) -> Dict[str, Any]:
    """
    Full Elliott Wave analysis on price series.

    Args:
        prices: List of closing prices (oldest first)
        dates: Optional date strings
        window: Pivot detection window size

    Returns:
        Dictionary with wave patterns, Fibonacci levels, and predictions
    """
    if len(prices) < 20:
        return {"error": "Need at least 20 data points", "patterns": []}

    highs_idx, lows_idx = _find_pivots(prices, window)
    pivots = _merge_pivots(prices, highs_idx, lows_idx)

    impulse = _check_impulse_wave(pivots)
    corrective = _check_corrective(pivots)

    recent_high = max(prices[-60:]) if len(prices) >= 60 else max(prices)
    recent_low = min(prices[-60:]) if len(prices) >= 60 else min(prices)

    fib_up = _fibonacci_levels(recent_high, recent_low, "up")
    fib_down = _fibonacci_levels(recent_high, recent_low, "down")

    position = _current_wave_position(prices, pivots)

    # Price targets based on wave analysis
    current = prices[-1]
    targets = {}
    if impulse:
        if impulse["type"] == "bullish_impulse":
            w1_mag = impulse["waves"]["wave_1"]["magnitude"]
            targets = {
                "conservative": round(current + w1_mag * 0.618, 2),
                "moderate": round(current + w1_mag * 1.0, 2),
                "aggressive": round(current + w1_mag * 1.618, 2),
            }
        else:
            w1_mag = impulse["waves"]["wave_1"]["magnitude"]
            targets = {
                "conservative": round(current - w1_mag * 0.618, 2),
                "moderate": round(current - w1_mag * 1.0, 2),
                "aggressive": round(current - w1_mag * 1.618, 2),
            }

    # Trend strength via price position relative to moving averages
    sma20 = np.mean(prices[-20:]) if len(prices) >= 20 else current
    sma50 = np.mean(prices[-50:]) if len(prices) >= 50 else current
    sma200 = np.mean(prices[-200:]) if len(prices) >= 200 else current

    trend = "strong_bullish" if current > sma20 > sma50 > sma200 else \
            "bullish" if current > sma50 else \
            "strong_bearish" if current < sma20 < sma50 < sma200 else \
            "bearish" if current < sma50 else "neutral"

    return {
        "current_price": current,
        "pivot_count": len(pivots),
        "impulse_wave": impulse,
        "corrective_wave": corrective,
        "fibonacci": {
            "support_levels": fib_down,
            "resistance_levels": fib_up,
        },
        "wave_position": position,
        "price_targets": targets,
        "trend": trend,
        "moving_averages": {
            "sma_20": round(sma20, 2),
            "sma_50": round(sma50, 2),
            "sma_200": round(sma200, 2),
        },
    }
