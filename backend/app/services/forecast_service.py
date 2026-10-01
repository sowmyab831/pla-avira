"""
Multi-horizon stock forecasting service.

Methods used per horizon:
  1d / 1w  — Exponential-smoothing + ATR-channel (fast, intraday-quality)
  1m / 3m  — Linear regression + MACD momentum extrapolation
  1y       — Trend decomposition (linear + seasonal) + mean-reversion band
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ema(values: List[float], span: int) -> List[float]:
    k = 2.0 / (span + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if not trs:
        return closes[-1] * 0.02
    return float(np.mean(trs[-period:]))


def _linear_regression(y: List[float]) -> Tuple[float, float]:
    """Returns (slope_per_bar, intercept)."""
    n = len(y)
    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _confidence_band(prices: List[float], forecast: List[float], multiplier: float = 1.5) -> Tuple[List[float], List[float]]:
    residuals = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    sigma = float(np.std(residuals)) if residuals else prices[-1] * 0.01
    half = sigma * multiplier
    return [round(f - half * (1 + i * 0.05), 2) for i, f in enumerate(forecast)], \
           [round(f + half * (1 + i * 0.05), 2) for i, f in enumerate(forecast)]


def _rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas[-period:]]
    losses = [abs(min(d, 0)) for d in deltas[-period:]]
    avg_gain = float(np.mean(gains)) if gains else 0
    avg_loss = float(np.mean(losses)) if losses else 1e-9
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    return round(100 - 100 / (1 + rs), 2)


def _macd_signal(closes: List[float]) -> str:
    if len(closes) < 26:
        return "neutral"
    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    macd_line = [f - s for f, s in zip(fast[-9:], slow[-9:])]
    sig_line = _ema(macd_line, 9)
    if macd_line[-1] > sig_line[-1] and macd_line[-2] <= sig_line[-2]:
        return "bullish_cross"
    if macd_line[-1] < sig_line[-1] and macd_line[-2] >= sig_line[-2]:
        return "bearish_cross"
    if macd_line[-1] > sig_line[-1]:
        return "bullish"
    return "bearish"


# ──────────────────────────────────────────────────────────────────────────────
# Horizon forecasters
# ──────────────────────────────────────────────────────────────────────────────

def _forecast_short(closes: List[float], highs: List[float], lows: List[float],
                    steps: int) -> Dict[str, Any]:
    """1d / 1w: EMA momentum + ATR channel."""
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    momentum = ema12[-1] - ema26[-1]
    daily_step = momentum / max(len(closes) * 0.1, 1)
    atr = _atr(highs, lows, closes)
    rsi = _rsi(closes)

    # Mean-reversion damping when RSI extreme
    if rsi > 70:
        daily_step = min(daily_step, 0)
    elif rsi < 30:
        daily_step = max(daily_step, 0)

    forecast = []
    price = closes[-1]
    for i in range(steps):
        price = round(price + daily_step * (0.9 ** i), 4)
        forecast.append(price)

    low_band, high_band = _confidence_band(closes, forecast, multiplier=atr / closes[-1] * 50)
    direction = "UP" if daily_step > 0 else "DOWN"
    magnitude = round(abs((forecast[-1] - closes[-1]) / closes[-1]) * 100, 2)

    return {
        "forecast": forecast,
        "low_band": low_band,
        "high_band": high_band,
        "direction": direction,
        "magnitude_pct": magnitude,
        "method": "EMA Momentum + ATR Channel",
        "rsi": rsi,
        "macd": _macd_signal(closes),
    }


def _forecast_medium(closes: List[float], highs: List[float], lows: List[float],
                     steps: int) -> Dict[str, Any]:
    """1m / 3m: Linear regression trend + MACD momentum."""
    n = min(60, len(closes))
    window = closes[-n:]
    slope, intercept = _linear_regression(window)

    # Project from end of window
    forecast = []
    for i in range(steps):
        projected = intercept + slope * (n + i)
        forecast.append(round(projected, 4))

    # MACD momentum adjustment
    macd = _macd_signal(closes)
    if macd in ("bullish", "bullish_cross"):
        forecast = [round(f * 1.005, 4) for f in forecast]
    elif macd in ("bearish", "bearish_cross"):
        forecast = [round(f * 0.995, 4) for f in forecast]

    low_band, high_band = _confidence_band(window, forecast, multiplier=2.0)
    direction = "UP" if slope > 0 else "DOWN"
    magnitude = round(abs((forecast[-1] - closes[-1]) / closes[-1]) * 100, 2)

    return {
        "forecast": forecast,
        "low_band": low_band,
        "high_band": high_band,
        "direction": direction,
        "magnitude_pct": magnitude,
        "method": "Linear Regression + MACD Momentum",
        "slope_per_bar": round(slope, 4),
        "macd": macd,
    }


def _forecast_long(closes: List[float], highs: List[float], lows: List[float],
                   steps: int) -> Dict[str, Any]:
    """1y: Trend decomposition + mean-reversion band."""
    n = min(252, len(closes))
    window = closes[-n:]

    slope, intercept = _linear_regression(window)

    # Detect approximate seasonality (52-week cycle)
    seasonal_amp = 0.0
    if len(window) >= 52:
        fft = np.fft.rfft(window - np.mean(window))
        dominant_freq_idx = int(np.argmax(np.abs(fft[1:])) + 1)
        seasonal_period = n / dominant_freq_idx if dominant_freq_idx > 0 else n
        seasonal_amp = float(np.std(window)) * 0.3
    else:
        seasonal_period = 52

    forecast = []
    for i in range(steps):
        trend = intercept + slope * (n + i)
        seasonal = seasonal_amp * np.sin(2 * np.pi * i / seasonal_period)
        forecast.append(round(float(trend + seasonal), 4))

    # Mean reversion toward 200-day SMA
    sma200 = float(np.mean(window[-200:])) if len(window) >= 200 else float(np.mean(window))
    forecast = [round(f * 0.95 + sma200 * 0.05, 4) for f in forecast]

    low_band, high_band = _confidence_band(window, forecast, multiplier=3.0)
    direction = "UP" if slope > 0 else "DOWN"
    magnitude = round(abs((forecast[-1] - closes[-1]) / closes[-1]) * 100, 2)

    return {
        "forecast": forecast,
        "low_band": low_band,
        "high_band": high_band,
        "direction": direction,
        "magnitude_pct": magnitude,
        "method": "Trend Decomposition + Seasonal FFT + Mean Reversion",
        "sma200": round(sma200, 2),
        "slope_per_bar": round(slope, 4),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def generate_forecasts(symbol: str) -> Dict[str, Any]:
    """
    Pull real-time yfinance data and generate forecasts across all horizons.

    Returns dict with keys: symbol, current_price, forecasts (per horizon).
    Each horizon contains forecast points, bands, direction, method, magnitude.
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)

        # Pull enough data for all horizons
        df = ticker.history(period="2y", interval="1d")
        if df is None or df.empty:
            return {"success": False, "error": "No data from yfinance"}

        closes = [float(x) for x in df["Close"].tolist()]
        highs = [float(x) for x in df["High"].tolist()]
        lows = [float(x) for x in df["Low"].tolist()]
        volumes = [int(x) for x in df["Volume"].tolist()]

        current_price = closes[-1]
        info = ticker.fast_info
        week52_high = float(getattr(info, "year_high", max(highs[-52:]) if len(highs) >= 52 else max(highs)))
        week52_low = float(getattr(info, "year_low", min(lows[-52:]) if len(lows) >= 52 else min(lows)))

        # Also fetch intraday data for 1h forecast
        try:
            intraday = ticker.history(period="5d", interval="5m")
            if intraday is not None and not intraday.empty:
                intra_closes = [float(x) for x in intraday["Close"].tolist()]
                intra_highs = [float(x) for x in intraday["High"].tolist()]
                intra_lows = [float(x) for x in intraday["Low"].tolist()]
            else:
                intra_closes, intra_highs, intra_lows = closes[-20:], highs[-20:], lows[-20:]
        except Exception:
            intra_closes, intra_highs, intra_lows = closes[-20:], highs[-20:], lows[-20:]

        horizons = {
            "1h": _forecast_short(intra_closes, intra_highs, intra_lows, steps=12),  # 12 x 5min = 1 hour
            "1d": _forecast_short(closes, highs, lows, steps=1),
            "1w": _forecast_short(closes, highs, lows, steps=5),
            "1m": _forecast_medium(closes, highs, lows, steps=21),
            "3m": _forecast_medium(closes, highs, lows, steps=63),
            "1y": _forecast_long(closes, highs, lows, steps=252),
        }

        # Attach summary labels to each horizon
        for h, data in horizons.items():
            data["target_price"] = round(data["forecast"][-1], 2)
            data["upside_pct"] = round((data["forecast"][-1] - current_price) / current_price * 100, 2)

        # Overall analyst-style rating — magnitude-weighted, long-term horizons matter more
        horizon_weights = {"1h": 0.02, "1d": 0.05, "1w": 0.08, "1m": 0.15, "3m": 0.25, "1y": 0.45}
        weighted_score = 0.0
        bull_count = 0
        for hkey, hdata in horizons.items():
            upside = hdata.get("upside_pct", 0)
            w = horizon_weights.get(hkey, 0.1)
            clamped = max(-30, min(30, upside))
            weighted_score += clamped * w
            if upside > 0.5:
                bull_count += 1

        if weighted_score >= 8:
            overall = "STRONG BUY"
        elif weighted_score >= 3:
            overall = "BUY"
        elif weighted_score >= -3:
            overall = "HOLD"
        elif weighted_score >= -8:
            overall = "SELL"
        else:
            overall = "STRONG SELL"

        # Price history for chart (last 90 days)
        recent = df.tail(90)
        price_history = [
            {
                "date": str(ts.date()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
            for ts, row in recent.iterrows()
        ]

        return {
            "success": True,
            "symbol": symbol.upper(),
            "current_price": round(current_price, 2),
            "week52_high": round(week52_high, 2),
            "week52_low": round(week52_low, 2),
            "overall_rating": overall,
            "bull_horizons": bull_count,
            "forecasts": horizons,
            "price_history": price_history,
            "rsi": _rsi(closes),
            "macd_signal": _macd_signal(closes),
        }

    except Exception as e:
        logger.error(f"Forecast error for {symbol}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
