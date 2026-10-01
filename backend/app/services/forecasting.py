"""
Forecasting Service
===================

Two scales of forecast, both compute-cheap so they run fine on an M4 16GB:

  * day_trade    — intraday 5-min / 15-min price path for the next trading day
                   with entry, stop, and take-profit levels derived from ATR
                   and recent support/resistance. Uses an EWMA-drift + ARIMA-
                   style autoregression on recent returns.

  * long_term    — 30 / 90 / 180-day trend forecast using Holt-Winters-like
                   exponential smoothing + optional XGBoost tilt (if a trained
                   per-symbol model exists at meridian/research/models).

Output is always a dict with a `points[]` price-path and a `signals{}` block
the frontend can render as an interactive chart with buy/sell zones.

NOTE: This is a *statistical* forecast. It's explicitly a tilt, not an oracle.
We expose `confidence_pct` and a `horizon` band the UI can shade.
"""
from __future__ import annotations

import asyncio
import logging
import math
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def _resolve_models_dir() -> Path:
    """Locate the XGBoost models directory across local dev + container layouts.

    Order of resolution:
      1. AVIRA_MODELS_DIR env var (explicit override)
      2. ../../../meridian/research/models    (local dev, repo root)
      3. /app/meridian/research/models        (Dockerfile COPY target)
      4. ./meridian/research/models           (cwd fallback)
    """
    import os as _os

    candidates = []
    env_dir = _os.environ.get("AVIRA_MODELS_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    here = Path(__file__).resolve()
    # backend/app/services/forecasting.py -> parents[3] = repo root
    candidates.append(here.parents[3] / "meridian" / "research" / "models")
    candidates.append(Path("/app/meridian/research/models"))
    candidates.append(Path.cwd() / "meridian" / "research" / "models")
    for c in candidates:
        if c.exists():
            return c
    # Return the first candidate so callers can still create / log it
    return candidates[0] if candidates else Path("./models")


MODELS_DIR = _resolve_models_dir()


# ─────────────────────────────────────────────────────────────────────────────
# Common helpers
# ─────────────────────────────────────────────────────────────────────────────

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _ewma_drift(returns: pd.Series, half_life: int = 10) -> float:
    """Exponentially-weighted mean return (drift) from a returns series."""
    alpha = 1 - 0.5 ** (1.0 / max(half_life, 1))
    return float(returns.ewm(alpha=alpha, adjust=False).mean().iloc[-1])


def _ewma_vol(returns: pd.Series, half_life: int = 20) -> float:
    alpha = 1 - 0.5 ** (1.0 / max(half_life, 1))
    return float(returns.ewm(alpha=alpha, adjust=False).std().iloc[-1])


def _last_n_support_resistance(close: pd.Series, n: int = 60) -> Tuple[float, float]:
    sub = close.iloc[-n:]
    return float(sub.min()), float(sub.max())


def _fmt(x: float | None, nd: int = 2) -> float | None:
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), nd)


def _build_xgb_features(df: pd.DataFrame) -> pd.DataFrame:
    """Reproduces meridian/research/train_xgboost.py's add_features() so the
    backend container doesn't need to import the training package."""
    df = df.copy()
    close = df["Close"]; high = df["High"]; low = df["Low"]; vol = df["Volume"]

    for n in (1, 3, 5, 10, 20):
        df[f"ret_{n}"] = close.pct_change(n)

    df["sma_5"]  = close.rolling(5).mean()
    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["ema_12"] = close.ewm(span=12, adjust=False).mean()
    df["ema_26"] = close.ewm(span=26, adjust=False).mean()
    df["sma20_dev"] = (close - df["sma_20"]) / df["sma_20"]
    df["sma50_dev"] = (close - df["sma_50"]) / df["sma_50"]

    df["macd"]        = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    tr = pd.concat(
        [(high - low),
         (high - close.shift()).abs(),
         (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr_14"] / close

    sd20 = close.rolling(20).std()
    df["bb_upper"] = df["sma_20"] + 2 * sd20
    df["bb_lower"] = df["sma_20"] - 2 * sd20
    df["bb_pct"]   = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    df["vol_z_20"] = (vol - vol.rolling(20).mean()) / vol.rolling(20).std()
    df["obv"] = (np.sign(close.diff().fillna(0)) * vol).cumsum()
    df["obv_z_20"] = (df["obv"] - df["obv"].rolling(20).mean()) / df["obv"].rolling(20).std()
    df["realized_vol_20"] = df["ret_1"].rolling(20).std() * np.sqrt(252)

    if isinstance(df.index, pd.DatetimeIndex):
        df["dow"]   = df.index.dayofweek
        df["month"] = df.index.month
    return df


def _try_load_xgb(symbol: str) -> Optional[Dict[str, Any]]:
    path = MODELS_DIR / f"{symbol.upper()}.pkl"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.debug("xgb load %s: %s", symbol, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Day-trade intraday forecast
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DayTradePlan:
    symbol: str
    as_of: str
    interval: str
    last_price: float
    direction: str                 # 'LONG' | 'SHORT' | 'FLAT'
    confidence_pct: float          # 0..100
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float
    expected_close: float
    expected_high: float
    expected_low: float
    volatility_pct: float
    support: float
    resistance: float
    points: List[Dict[str, Any]]   # forecasted path
    history: List[Dict[str, Any]]  # recent intraday bars
    rationale: str
    model_stack: List[str]         # transparency

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


async def forecast_day_trade(symbol: str, interval: str = "15m") -> Dict[str, Any]:
    """
    Produce an intraday forecast for today's session.

    Model: EWMA drift + AR(1) on recent intraday returns, clipped by ATR
    bounds; buy/sell levels from support/resistance + ATR multiples.
    """
    try:
        import yfinance as yf  # noqa
    except ImportError:
        return {"error": "yfinance not installed"}

    loop = asyncio.get_event_loop()
    # 10 trading days of intraday bars (yfinance caps at ~60 days for 15m)
    df = await loop.run_in_executor(
        None,
        lambda: _yf_download(symbol, period="10d", interval=interval),
    )
    if df is None or df.empty or len(df) < 30:
        # Graceful fallback — downsample daily into an intraday-shape payload so
        # the UI still renders a plan during Yahoo rate-limits.
        return await _day_trade_fallback_from_daily(symbol, interval)

    close = df["Close"].astype(float)
    rets = close.pct_change().dropna()
    drift = _ewma_drift(rets, half_life=12)
    vol = _ewma_vol(rets, half_life=20)
    # AR(1) coefficient on recent returns (stabilises the path)
    phi = float(rets.iloc[-50:].autocorr(lag=1) or 0.0)
    phi = max(-0.35, min(0.35, phi))

    # How many bars between now and today's close
    bars_per_day = {"1m": 390, "5m": 78, "15m": 26, "30m": 13, "60m": 7, "1h": 7}.get(interval, 26)
    completed_today = _bars_completed_today(df, bars_per_day)
    bars_ahead = max(4, bars_per_day - completed_today)

    last_price = float(close.iloc[-1])
    last_ret = float(rets.iloc[-1]) if len(rets) else 0.0
    atr = float(_atr(df, 14).iloc[-1])
    atr_pct = atr / last_price if last_price else 0.0

    # Forecast path: iterate r_t = drift + phi*(r_{t-1}-drift) + small noise
    path: List[Tuple[datetime, float]] = []
    px = last_price
    r_prev = last_ret
    step = _interval_to_timedelta(interval)
    t_now = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else datetime.utcnow()
    for i in range(bars_ahead):
        r_next = drift + phi * (r_prev - drift)
        px = px * (1 + r_next)
        r_prev = r_next
        path.append((t_now + step * (i + 1), px))

    expected_close = path[-1][1] if path else last_price
    # One-sigma band over the session
    band = last_price * vol * math.sqrt(bars_ahead)

    support, resistance = _last_n_support_resistance(close, n=min(60, len(close)))
    direction_score = (expected_close - last_price) / last_price  # fractional

    # Confidence from magnitude vs vol noise floor
    noise = max(1e-4, vol * math.sqrt(bars_ahead))
    snr = abs(direction_score) / noise
    confidence_pct = float(min(95.0, 50.0 + 45.0 * math.tanh(snr)))

    if direction_score > 0.001:
        direction = "LONG"
    elif direction_score < -0.001:
        direction = "SHORT"
    else:
        direction = "FLAT"

    # Entry / stop / targets (risk 1× ATR, reward 1.5× / 2.5× ATR)
    if direction == "LONG":
        entry = last_price
        stop_loss = max(support, last_price - 1.0 * atr)
        tp1 = last_price + 1.5 * atr
        tp2 = last_price + 2.5 * atr
    elif direction == "SHORT":
        entry = last_price
        stop_loss = min(resistance, last_price + 1.0 * atr)
        tp1 = last_price - 1.5 * atr
        tp2 = last_price - 2.5 * atr
    else:
        entry = last_price
        stop_loss = last_price - 1.0 * atr
        tp1 = last_price + 1.0 * atr
        tp2 = last_price + 1.5 * atr

    rr = abs((tp1 - entry) / (entry - stop_loss)) if entry != stop_loss else 0.0

    # Plot history (last ~40 bars) + forecast
    history_bars = [
        {"t": str(idx), "price": _fmt(float(v))}
        for idx, v in close.iloc[-40:].items()
    ]
    forecast_points = [
        {"t": t.isoformat(), "price": _fmt(p), "upper": _fmt(p + band), "lower": _fmt(p - band)}
        for t, p in path
    ]

    rationale = (
        f"Intraday drift {drift*100:.3f}% / bar, AR(1) φ={phi:.2f}, vol {vol*100:.2f}%; "
        f"ATR={atr:.2f} ({atr_pct*100:.2f}%). Bias {direction.lower()} over {bars_ahead} "
        f"bars to ~{expected_close:.2f} (±{band:.2f}). "
        f"Support {support:.2f} / resistance {resistance:.2f}."
    )

    plan = DayTradePlan(
        symbol=symbol.upper(),
        as_of=datetime.utcnow().isoformat(),
        interval=interval,
        last_price=_fmt(last_price) or 0.0,
        direction=direction,
        confidence_pct=_fmt(confidence_pct, 1) or 0.0,
        entry=_fmt(entry) or 0.0,
        stop_loss=_fmt(stop_loss) or 0.0,
        take_profit_1=_fmt(tp1) or 0.0,
        take_profit_2=_fmt(tp2) or 0.0,
        risk_reward=_fmt(rr, 2) or 0.0,
        expected_close=_fmt(expected_close) or 0.0,
        expected_high=_fmt(expected_close + band) or 0.0,
        expected_low=_fmt(expected_close - band) or 0.0,
        volatility_pct=_fmt(vol * 100, 2) or 0.0,
        support=_fmt(support) or 0.0,
        resistance=_fmt(resistance) or 0.0,
        points=forecast_points,
        history=history_bars,
        rationale=rationale,
        model_stack=[
            "statistical:ewma_drift",
            "statistical:ar1",
            "indicator:atr14",
            "indicator:support_resistance",
        ],
    )
    return plan.as_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Long-term forecast (30 / 90 / 180 day)
# ─────────────────────────────────────────────────────────────────────────────

async def forecast_long_term(symbol: str, horizons: Tuple[int, int, int] = (30, 90, 180)) -> Dict[str, Any]:
    try:
        import yfinance as yf  # noqa
    except ImportError:
        return {"error": "yfinance not installed"}

    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(
        None,
        lambda: _yf_download(symbol, period="2y", interval="1d"),
    )
    if df is None or df.empty or len(df) < 120:
        return {"symbol": symbol.upper(), "error": "not enough daily history"}

    close = df["Close"].astype(float)
    rets = close.pct_change().dropna()
    drift = float(rets.ewm(span=60, adjust=False).mean().iloc[-1])
    vol = float(rets.ewm(span=60, adjust=False).std().iloc[-1])

    # Optional XGB tilt — bumps drift if per-symbol model predicts UP
    xgb = _try_load_xgb(symbol)
    xgb_tilt_used = False
    xgb_info: Optional[Dict[str, Any]] = None
    if xgb:
        try:
            feats = _build_xgb_features(df).dropna()
            if not feats.empty:
                p_up = float(xgb["model"].predict_proba(feats.iloc[[-1]][xgb["features"]])[0, 1])
                # map p_up [0,1] → small drift tilt ±0.001/day
                drift += (p_up - 0.5) * 0.002
                xgb_tilt_used = True
                xgb_info = {
                    "p_up_next_day": round(p_up, 3),
                    "test_auc": xgb.get("report", {}).get("test_auc"),
                    "period": xgb.get("trained_with_period"),
                }
        except Exception as e:
            logger.debug("xgb tilt skipped %s: %s", symbol, e)

    last_price = float(close.iloc[-1])
    forecasts: Dict[str, Any] = {}
    path_all: List[Dict[str, Any]] = []

    max_h = max(horizons)
    px = last_price
    for d in range(1, max_h + 1):
        px = px * (1 + drift)
        band = last_price * vol * math.sqrt(d)
        t = datetime.utcnow() + timedelta(days=d)
        path_all.append({
            "t": t.date().isoformat(),
            "price": _fmt(px),
            "upper": _fmt(px + band),
            "lower": _fmt(px - band),
        })

    for h in horizons:
        pt = path_all[h - 1]
        target = pt["price"]
        lo = pt["lower"]
        hi = pt["upper"]
        ret_pct = (target - last_price) / last_price * 100 if last_price else 0.0
        forecasts[f"{h}d"] = {
            "target_price": target,
            "expected_return_pct": _fmt(ret_pct, 2),
            "band_low": lo,
            "band_high": hi,
            "probability_up": _fmt(_prob_up(last_price, target, lo, hi), 3),
        }

    # Trade plan (swing) off the 30d forecast
    target_30d = forecasts["30d"]["target_price"] or last_price
    atr = float(_atr(df, 14).iloc[-1])
    if target_30d > last_price:
        direction = "BUY"
        entry = last_price
        stop_loss = last_price - 2.0 * atr
        tp1 = last_price + 2.0 * atr
        tp2 = target_30d
    elif target_30d < last_price:
        direction = "SELL"
        entry = last_price
        stop_loss = last_price + 2.0 * atr
        tp1 = last_price - 2.0 * atr
        tp2 = target_30d
    else:
        direction = "HOLD"
        entry = last_price
        stop_loss = last_price - 2.0 * atr
        tp1 = last_price + 2.0 * atr
        tp2 = last_price + 3.0 * atr

    rr = abs((tp1 - entry) / (entry - stop_loss)) if entry != stop_loss else 0.0

    history = [
        {"t": str(idx.date()), "price": _fmt(float(v))}
        for idx, v in close.iloc[-180:].items()
    ]

    model_stack = [
        "statistical:ewma_drift(60d)",
        "statistical:ewma_vol(60d)",
        "indicator:atr14",
    ]
    if xgb_tilt_used:
        model_stack.append("ml:xgboost_2y_direction_tilt")

    return {
        "symbol": symbol.upper(),
        "as_of": datetime.utcnow().isoformat(),
        "last_price": _fmt(last_price),
        "forecasts": forecasts,
        "path": path_all,
        "history": history,
        "swing_trade": {
            "direction": direction,
            "entry": _fmt(entry),
            "stop_loss": _fmt(stop_loss),
            "take_profit_1": _fmt(tp1),
            "take_profit_2": _fmt(tp2),
            "risk_reward": _fmt(rr, 2),
        },
        "xgb": xgb_info,
        "model_stack": model_stack,
        "rationale": (
            f"Daily drift {drift*100:.3f}%, 60d vol {vol*100:.2f}%. "
            f"30d target {forecasts['30d']['target_price']} "
            f"({forecasts['30d']['expected_return_pct']}% vs last {last_price:.2f}). "
            f"XGBoost tilt: {'applied' if xgb_tilt_used else 'no trained model'}. "
            "Not financial advice."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Combined / convenience
# ─────────────────────────────────────────────────────────────────────────────

async def forecast_combined(symbol: str, interval: str = "15m") -> Dict[str, Any]:
    day, longt = await asyncio.gather(
        forecast_day_trade(symbol, interval=interval),
        forecast_long_term(symbol),
        return_exceptions=True,
    )
    return {
        "symbol": symbol.upper(),
        "day_trade": day if isinstance(day, dict) else {"error": str(day)},
        "long_term": longt if isinstance(longt, dict) else {"error": str(longt)},
        "generated_at": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal utilities
# ─────────────────────────────────────────────────────────────────────────────

def _yf_download(symbol: str, period: str, interval: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def _interval_to_timedelta(interval: str) -> timedelta:
    unit = interval[-1]
    n = int(interval[:-1]) if interval[:-1].isdigit() else 1
    if unit == "m": return timedelta(minutes=n)
    if unit == "h": return timedelta(hours=n)
    if unit == "d": return timedelta(days=n)
    return timedelta(minutes=15)


def _bars_completed_today(df: pd.DataFrame, bars_per_day: int) -> int:
    try:
        last_day = df.index[-1].date() if hasattr(df.index[-1], "date") else None
        if last_day is None:
            return bars_per_day // 2
        mask = [ix.date() == last_day for ix in df.index]
        return sum(mask)
    except Exception:
        return bars_per_day // 2


async def _day_trade_fallback_from_daily(symbol: str, interval: str) -> Dict[str, Any]:
    """When Yahoo rate-limits intraday, synthesise a plan from daily bars so
    the UI always has something to render. Clearly marked as degraded."""
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, lambda: _yf_download(symbol, period="3mo", interval="1d"))
    if df is None or df.empty or len(df) < 20:
        return {"symbol": symbol.upper(), "error": "no data (rate-limited and daily fetch failed)"}

    close = df["Close"].astype(float)
    rets = close.pct_change().dropna()
    drift = _ewma_drift(rets, half_life=8)
    vol = _ewma_vol(rets, half_life=20)
    atr = float(_atr(df, 14).iloc[-1])
    last_price = float(close.iloc[-1])
    support, resistance = _last_n_support_resistance(close, n=20)

    # Project ~26 synthetic 15-min bars covering the next session
    bars_ahead = 26
    step = _interval_to_timedelta(interval)
    t_now = datetime.utcnow()
    px = last_price
    # convert daily drift / vol to intraday-ish (each synthetic bar ≈ 1/26 of a day)
    bar_drift = drift / bars_ahead
    bar_vol = vol / math.sqrt(bars_ahead)
    path = []
    for i in range(bars_ahead):
        px = px * (1 + bar_drift)
        band = last_price * bar_vol * math.sqrt(i + 1)
        path.append({
            "t": (t_now + step * (i + 1)).isoformat(),
            "price": _fmt(px),
            "upper": _fmt(px + band),
            "lower": _fmt(px - band),
        })
    expected_close = path[-1]["price"]
    direction_score = ((expected_close or last_price) - last_price) / last_price
    direction = "LONG" if direction_score > 0.0005 else "SHORT" if direction_score < -0.0005 else "FLAT"

    entry = last_price
    if direction == "LONG":
        stop_loss = max(support, last_price - 1.0 * atr)
        tp1, tp2 = last_price + 1.2 * atr, last_price + 2.0 * atr
    elif direction == "SHORT":
        stop_loss = min(resistance, last_price + 1.0 * atr)
        tp1, tp2 = last_price - 1.2 * atr, last_price - 2.0 * atr
    else:
        stop_loss = last_price - atr
        tp1, tp2 = last_price + atr, last_price + 1.5 * atr

    rr = abs((tp1 - entry) / (entry - stop_loss)) if entry != stop_loss else 0.0

    return {
        "symbol": symbol.upper(),
        "as_of": datetime.utcnow().isoformat(),
        "interval": interval,
        "degraded": True,
        "degraded_reason": "intraday rate-limited; synthesised from daily bars",
        "last_price": _fmt(last_price),
        "direction": direction,
        "confidence_pct": 40.0,
        "entry": _fmt(entry),
        "stop_loss": _fmt(stop_loss),
        "take_profit_1": _fmt(tp1),
        "take_profit_2": _fmt(tp2),
        "risk_reward": _fmt(rr, 2),
        "expected_close": expected_close,
        "volatility_pct": _fmt(vol * 100, 2),
        "support": _fmt(support),
        "resistance": _fmt(resistance),
        "points": path,
        "history": [{"t": str(i.date()), "price": _fmt(float(v))} for i, v in close.iloc[-40:].items()],
        "rationale": f"Synthetic intraday path from daily drift {drift*100:.3f}%/day. ATR={atr:.2f}. Use with caution.",
        "model_stack": ["fallback:daily_drift", "indicator:atr14", "indicator:support_resistance"],
    }


def _prob_up(last: float, mid: float, lo: float | None, hi: float | None) -> float:
    """Crude probability the symbol is higher than `last` at horizon h,
    under a Gaussian with mean=mid and std=(hi-lo)/2."""
    if lo is None or hi is None or hi <= lo:
        return 0.5
    sigma = max(1e-9, (hi - lo) / 2.0)
    z = (mid - last) / sigma
    # normal CDF via erf
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))
