"""
Tests for the forecasting service. Network-dependent (yfinance).
We tolerate Yahoo rate-limits by also accepting the documented `error` /
`degraded` shapes.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.services.forecasting import (
    _atr,
    _ewma_drift,
    _ewma_vol,
    _last_n_support_resistance,
    _prob_up,
    forecast_combined,
    forecast_day_trade,
    forecast_long_term,
)


# ─── pure helpers (deterministic, no network) ──────────────────────────────

def _synthetic_df(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.012, n)
    close = 100 * np.cumprod(1 + rets)
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    return pd.DataFrame(
        {"Close": close, "High": high, "Low": low, "Volume": rng.integers(1_000_000, 5_000_000, n)},
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )


def test_atr_is_positive_and_bounded():
    df = _synthetic_df(120)
    atr = _atr(df, 14).dropna()
    assert (atr > 0).all()
    assert atr.iloc[-1] < df["Close"].iloc[-1]  # ATR << price


def test_ewma_drift_handles_constant_returns():
    s = pd.Series([0.001] * 50)
    assert math.isclose(_ewma_drift(s), 0.001, rel_tol=1e-6)


def test_ewma_vol_rises_with_noise():
    s_lo = pd.Series(np.random.default_rng(1).normal(0, 0.005, 200))
    s_hi = pd.Series(np.random.default_rng(2).normal(0, 0.05, 200))
    assert _ewma_vol(s_hi) > _ewma_vol(s_lo)


def test_support_resistance_orders():
    df = _synthetic_df(80)
    s, r = _last_n_support_resistance(df["Close"], n=60)
    assert s <= r


def test_prob_up_monotonic_in_drift():
    base = _prob_up(100.0, 100.0, 90.0, 110.0)
    up = _prob_up(100.0, 105.0, 95.0, 115.0)
    down = _prob_up(100.0, 95.0, 85.0, 105.0)
    assert math.isclose(base, 0.5, abs_tol=0.05)
    assert up > base > down


# ─── async network forecasts ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_long_term_returns_horizons():
    out = await forecast_long_term("AAPL")
    if out.get("error"):
        pytest.skip(f"network/rate-limit: {out['error']}")
    assert {"30d", "90d", "180d"}.issubset(out["forecasts"].keys())
    f30 = out["forecasts"]["30d"]
    for k in ("target_price", "expected_return_pct", "band_low", "band_high", "probability_up"):
        assert k in f30
    assert out["swing_trade"]["direction"] in {"BUY", "SELL", "HOLD"}
    assert isinstance(out["model_stack"], list) and out["model_stack"]


@pytest.mark.asyncio
async def test_day_trade_path_or_degraded():
    out = await forecast_day_trade("AAPL")
    # Either we got a normal response or a documented degraded fallback.
    if out.get("error"):
        pytest.skip(f"network/rate-limit: {out['error']}")
    assert "direction" in out
    assert out["direction"] in {"LONG", "SHORT", "FLAT"}
    assert isinstance(out["points"], list)
    assert len(out["points"]) > 0
    # Risk:reward must be a non-negative number
    assert out["risk_reward"] is None or out["risk_reward"] >= 0


@pytest.mark.asyncio
async def test_combined_returns_both_blocks():
    out = await forecast_combined("AAPL")
    assert "day_trade" in out and "long_term" in out
