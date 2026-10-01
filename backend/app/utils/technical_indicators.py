"""
Technical Indicators for Stock Analysis.

Provides RSI, MACD, Bollinger Bands, Support/Resistance, Elliott Wave,
and other technical analysis tools used by the Quant Agent.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    RSI > 70 = overbought, RSI < 30 = oversold
    """
    if len(prices) < period + 1:
        return 50.0

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        return 100.0

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi), 2)


def calculate_macd(
    prices: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, float]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Returns MACD line, signal line, and histogram.
    """
    if len(prices) < slow + signal:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    arr = np.array(prices, dtype=float)

    ema_fast = _ema(arr, fast)
    ema_slow = _ema(arr, slow)

    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line[slow - fast:], signal)

    # Align lengths
    macd_val = float(macd_line[-1])
    signal_val = float(signal_line[-1])

    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(macd_val - signal_val, 4),
        "trend": "bullish" if macd_val > signal_val else "bearish",
    }


def calculate_bollinger_bands(
    prices: List[float], period: int = 20, std_dev: float = 2.0
) -> Dict[str, float]:
    """
    Calculate Bollinger Bands.
    
    Price near upper band = potential resistance / overbought
    Price near lower band = potential support / oversold
    """
    if len(prices) < period:
        p = prices[-1] if prices else 0
        return {"upper": p, "middle": p, "lower": p, "bandwidth": 0.0}

    arr = np.array(prices[-period:], dtype=float)
    middle = float(np.mean(arr))
    std = float(np.std(arr))
    upper = middle + std_dev * std
    lower = middle - std_dev * std

    bandwidth = ((upper - lower) / middle) * 100 if middle > 0 else 0

    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "bandwidth": round(bandwidth, 2),
        "position": _band_position(prices[-1], upper, lower),
    }


def calculate_support_resistance(
    prices: List[float], window: int = 5
) -> Dict[str, Any]:
    """
    Calculate support and resistance levels using local min/max.
    """
    if len(prices) < window * 2 + 1:
        p = prices[-1] if prices else 0
        return {"support": [p * 0.95], "resistance": [p * 1.05]}

    arr = np.array(prices, dtype=float)
    supports = []
    resistances = []

    for i in range(window, len(arr) - window):
        # Local minimum = support
        if arr[i] == min(arr[i - window: i + window + 1]):
            supports.append(round(float(arr[i]), 2))
        # Local maximum = resistance
        if arr[i] == max(arr[i - window: i + window + 1]):
            resistances.append(round(float(arr[i]), 2))

    # Keep strongest (most recent) levels
    supports = sorted(set(supports))[-3:]
    resistances = sorted(set(resistances))[-3:]

    current = float(arr[-1])

    return {
        "support": supports if supports else [round(current * 0.95, 2)],
        "resistance": resistances if resistances else [round(current * 1.05, 2)],
        "nearest_support": max([s for s in supports if s < current], default=round(current * 0.95, 2)),
        "nearest_resistance": min([r for r in resistances if r > current], default=round(current * 1.05, 2)),
    }


def calculate_moving_averages(prices: List[float]) -> Dict[str, Optional[float]]:
    """Calculate common moving averages: SMA 20, 50, 200 and EMA 12, 26."""
    result = {}
    arr = np.array(prices, dtype=float)

    for period in [20, 50, 200]:
        if len(arr) >= period:
            result[f"sma_{period}"] = round(float(np.mean(arr[-period:])), 2)
        else:
            result[f"sma_{period}"] = None

    for period in [12, 26]:
        if len(arr) >= period:
            ema = _ema(arr, period)
            result[f"ema_{period}"] = round(float(ema[-1]), 2)
        else:
            result[f"ema_{period}"] = None

    # Golden cross / death cross
    if result.get("sma_50") and result.get("sma_200"):
        if result["sma_50"] > result["sma_200"]:
            result["cross_signal"] = "golden_cross"
        else:
            result["cross_signal"] = "death_cross"

    return result


def calculate_atr(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> float:
    """Calculate Average True Range for volatility measurement."""
    if len(highs) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return round(float(np.mean(true_ranges)), 2)

    atr = float(np.mean(true_ranges[-period:]))
    return round(atr, 2)


def calculate_stochastic(
    highs: List[float], lows: List[float], closes: List[float],
    k_period: int = 14, d_period: int = 3
) -> Dict[str, float]:
    """Calculate Stochastic Oscillator (%K and %D)."""
    if len(closes) < k_period:
        return {"k": 50.0, "d": 50.0, "signal": "neutral"}

    highest_high = max(highs[-k_period:])
    lowest_low = min(lows[-k_period:])

    if highest_high == lowest_low:
        k = 50.0
    else:
        k = ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100

    # Simplified %D (would need historical %K values for proper SMA)
    d = k  # Approximate

    signal = "overbought" if k > 80 else "oversold" if k < 20 else "neutral"

    return {"k": round(k, 2), "d": round(d, 2), "signal": signal}


def calculate_vwap(
    prices: List[float], volumes: List[float]
) -> float:
    """Calculate Volume Weighted Average Price."""
    if not prices or not volumes or len(prices) != len(volumes):
        return prices[-1] if prices else 0.0

    total_pv = sum(p * v for p, v in zip(prices, volumes))
    total_v = sum(volumes)

    if total_v == 0:
        return prices[-1]

    return round(total_pv / total_v, 2)


def get_full_technical_analysis(
    prices: List[float],
    highs: Optional[List[float]] = None,
    lows: Optional[List[float]] = None,
    volumes: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Run all technical indicators and return a comprehensive analysis.
    """
    if not prices:
        return {"error": "No price data provided"}

    highs = highs or prices
    lows = lows or prices
    volumes = volumes or [0] * len(prices)

    current_price = prices[-1]
    rsi = calculate_rsi(prices)
    macd = calculate_macd(prices)
    bollinger = calculate_bollinger_bands(prices)
    sr = calculate_support_resistance(prices)
    mas = calculate_moving_averages(prices)
    atr = calculate_atr(highs, lows, prices)
    stoch = calculate_stochastic(highs, lows, prices)

    # Composite signal
    signals = []
    if rsi < 30:
        signals.append("oversold")
    elif rsi > 70:
        signals.append("overbought")
    if macd["trend"] == "bullish":
        signals.append("macd_bullish")
    else:
        signals.append("macd_bearish")
    if bollinger["position"] == "below_lower":
        signals.append("below_bollinger")
    elif bollinger["position"] == "above_upper":
        signals.append("above_bollinger")

    bullish_count = sum(1 for s in signals if "bullish" in s or "oversold" in s or "below" in s)
    bearish_count = sum(1 for s in signals if "bearish" in s or "overbought" in s or "above" in s)

    if bullish_count > bearish_count:
        overall = "bullish"
    elif bearish_count > bullish_count:
        overall = "bearish"
    else:
        overall = "neutral"

    return {
        "current_price": current_price,
        "rsi": rsi,
        "macd": macd,
        "bollinger_bands": bollinger,
        "support_resistance": sr,
        "moving_averages": mas,
        "atr": atr,
        "stochastic": stoch,
        "signals": signals,
        "overall_signal": overall,
        "strength": max(bullish_count, bearish_count) / max(len(signals), 1),
    }


# --- Internal helpers ---

def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    alpha = 2 / (period + 1)
    ema = np.zeros_like(data, dtype=float)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


def _band_position(price: float, upper: float, lower: float) -> str:
    """Determine price position relative to Bollinger Bands."""
    if price > upper:
        return "above_upper"
    elif price < lower:
        return "below_lower"
    mid = (upper + lower) / 2
    if price > mid:
        return "upper_half"
    return "lower_half"
