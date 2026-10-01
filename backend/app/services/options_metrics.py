"""
Options deep metrics — deterministic computation from yfinance option chains.

Implements catalog groups 451–500: IV rank, term structure, skew, put/call OI,
max pain, unusual activity flags. No AI. US options only (yfinance has no
Indian option chains — returns coverage: none for IN symbols).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 600  # 10 min


def compute_options_metrics(symbol: str) -> Dict[str, Any]:
    """Compute deterministic options positioning metrics for a symbol."""
    cache_key = symbol.upper()
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        t = yf.Ticker(symbol)
        expirations = t.options or []
        if not expirations:
            return {"symbol": symbol, "coverage": "none",
                    "note": "No listed options for this symbol"}
        spot = (t.fast_info or {}).get("last_price") or (t.info or {}).get("currentPrice")
        if not spot:
            hist = t.history(period="1d")
            spot = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if not spot:
            return {"symbol": symbol, "coverage": "none", "note": "No spot price"}

        near = t.option_chain(expirations[0])
        far = t.option_chain(expirations[min(3, len(expirations) - 1)]) if len(expirations) > 1 else None
    except Exception as e:
        logger.warning(f"options_metrics fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "coverage": "none", "error": str(e)[:120]}

    calls, puts = near.calls, near.puts

    # ── ATM IV + term structure ──────────────────────────────────────────
    atm_iv_near = _atm_iv(calls, puts, spot)
    atm_iv_far = None
    if far is not None:
        atm_iv_far = _atm_iv(far.calls, far.puts, spot)
    term_slope = None
    if atm_iv_near and atm_iv_far:
        term_slope = round(atm_iv_far - atm_iv_near, 4)  # positive = contango (normal)

    # ── 25-delta-style skew (approx via OTM strikes at ±10%) ─────────────
    otm_put_iv = _iv_at_strike(puts, spot * 0.90)
    otm_call_iv = _iv_at_strike(calls, spot * 1.10)
    skew = None
    if otm_put_iv and otm_call_iv:
        skew = round(otm_put_iv - otm_call_iv, 4)  # positive = downside fear premium

    # ── Put/Call open interest + volume ratios ───────────────────────────
    call_oi = float(calls["openInterest"].fillna(0).sum())
    put_oi = float(puts["openInterest"].fillna(0).sum())
    call_vol = float(calls["volume"].fillna(0).sum())
    put_vol = float(puts["volume"].fillna(0).sum())
    pc_oi = round(put_oi / call_oi, 2) if call_oi > 0 else None
    pc_vol = round(put_vol / call_vol, 2) if call_vol > 0 else None

    # ── Max pain (strike minimizing total option payout at expiry) ───────
    max_pain = _max_pain(calls, puts)

    # ── Unusual activity: volume >> open interest on individual strikes ──
    unusual = _unusual_activity(calls, "CALL") + _unusual_activity(puts, "PUT")
    unusual.sort(key=lambda u: u["vol_oi_ratio"], reverse=True)

    result = {
        "symbol": symbol.upper(),
        "coverage": "full",
        "as_of": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "spot": round(float(spot), 2),
        "near_expiration": expirations[0],
        "metrics": {
            "atm_iv_near_pct": round(atm_iv_near * 100, 1) if atm_iv_near else None,
            "atm_iv_far_pct": round(atm_iv_far * 100, 1) if atm_iv_far else None,
            "term_structure_slope": term_slope,
            "term_structure_state": (
                "contango_normal" if term_slope and term_slope > 0
                else "backwardation_stress" if term_slope and term_slope < 0 else None
            ),
            "skew_10pct_otm": skew,
            "skew_state": (
                "downside_fear" if skew and skew > 0.03
                else "call_chase" if skew and skew < -0.03
                else "balanced" if skew is not None else None
            ),
            "put_call_oi_ratio": pc_oi,
            "put_call_volume_ratio": pc_vol,
            "max_pain_strike": max_pain,
            "max_pain_vs_spot_pct": (
                round((max_pain - spot) / spot * 100, 2) if max_pain else None
            ),
            "total_call_oi": int(call_oi),
            "total_put_oi": int(put_oi),
        },
        "unusual_activity": unusual[:5],
    }
    _CACHE[cache_key] = {"data": result, "ts": time.time()}
    return result


def _atm_iv(calls, puts, spot: float) -> Optional[float]:
    """Average implied vol of the call+put closest to spot."""
    try:
        ivs = []
        for df in (calls, puts):
            if df is None or df.empty:
                continue
            df = df.dropna(subset=["impliedVolatility"])
            if df.empty:
                continue
            nearest = df.iloc[(df["strike"] - spot).abs().argsort()[:1]]
            iv = float(nearest["impliedVolatility"].iloc[0])
            if 0 < iv < 5:
                ivs.append(iv)
        return sum(ivs) / len(ivs) if ivs else None
    except Exception:
        return None


def _iv_at_strike(df, target_strike: float) -> Optional[float]:
    try:
        if df is None or df.empty:
            return None
        df = df.dropna(subset=["impliedVolatility"])
        if df.empty:
            return None
        nearest = df.iloc[(df["strike"] - target_strike).abs().argsort()[:1]]
        iv = float(nearest["impliedVolatility"].iloc[0])
        return iv if 0 < iv < 5 else None
    except Exception:
        return None


def _max_pain(calls, puts) -> Optional[float]:
    """Strike where total intrinsic payout to option holders is minimized."""
    try:
        strikes = sorted(set(calls["strike"]) | set(puts["strike"]))
        if not strikes:
            return None
        call_oi = calls.set_index("strike")["openInterest"].fillna(0)
        put_oi = puts.set_index("strike")["openInterest"].fillna(0)
        best_strike, best_pain = None, float("inf")
        for s in strikes:
            call_pain = sum(max(0, s - k) * call_oi.get(k, 0) for k in call_oi.index)
            put_pain = sum(max(0, k - s) * put_oi.get(k, 0) for k in put_oi.index)
            total = call_pain + put_pain
            if total < best_pain:
                best_pain, best_strike = total, s
        return float(best_strike) if best_strike is not None else None
    except Exception:
        return None


def _unusual_activity(df, side: str) -> List[Dict]:
    """Strikes where today's volume is >3x open interest (min 500 contracts)."""
    out = []
    try:
        if df is None or df.empty:
            return out
        for _, row in df.iterrows():
            vol = row.get("volume") or 0
            oi = row.get("openInterest") or 0
            if vol >= 500 and oi > 0 and vol / oi > 3:
                out.append({
                    "side": side,
                    "strike": float(row["strike"]),
                    "volume": int(vol),
                    "open_interest": int(oi),
                    "vol_oi_ratio": round(vol / oi, 1),
                })
    except Exception:
        pass
    return out
