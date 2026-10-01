"""
Fundamental deep metrics — deterministic computation from yfinance statements.

Implements the fundamental groups of the 500-dimension research catalog
(growth, profitability, balance-sheet vulnerability, valuation, earnings,
ownership). No AI. Missing data returns None ("n/a"), never fabricated.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 900  # 15 min


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    try:
        if a is None or b is None or b == 0:
            return None
        return a / b
    except Exception:
        return None


def _row(df, *names) -> Optional[Any]:
    """Fetch first matching row (Series across periods) from a statement DataFrame."""
    if df is None or getattr(df, "empty", True):
        return None
    for name in names:
        if name in df.index:
            return df.loc[name]
    return None


def _latest(series) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    try:
        v = series.iloc[0]
        return None if v is None or (v != v) else float(v)  # NaN check
    except Exception:
        return None


def _prior(series, idx: int = 1) -> Optional[float]:
    if series is None or len(series) <= idx:
        return None
    try:
        v = series.iloc[idx]
        return None if v is None or (v != v) else float(v)
    except Exception:
        return None


def _pct_change(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 2)


def compute_fundamental_metrics(symbol: str) -> Dict[str, Any]:
    """Compute grouped deterministic fundamental metrics for a symbol."""
    cache_key = symbol.upper()
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        fin = t.financials          # annual income statement
        qfin = t.quarterly_financials
        bs = t.balance_sheet
        cf = t.cashflow
    except Exception as e:
        logger.warning(f"fundamental_metrics fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "error": "data_unavailable", "groups": {}}

    # ── Growth (catalog 001–025) ─────────────────────────────────────────
    rev = _row(fin, "Total Revenue")
    qrev = _row(qfin, "Total Revenue")
    rev_growth = _pct_change(_latest(rev), _prior(rev))
    qrev_growth = _pct_change(_latest(qrev), _prior(qrev, 4) or _prior(qrev))
    prev_qrev_growth = _pct_change(_prior(qrev), _prior(qrev, 5) or _prior(qrev, 2))
    growth = {
        "revenue_growth_yoy_pct": rev_growth,
        "revenue_growth_qoq_yoy_pct": qrev_growth,
        "revenue_acceleration_pp": (
            round(qrev_growth - prev_qrev_growth, 2)
            if qrev_growth is not None and prev_qrev_growth is not None else None
        ),
    }

    # ── Profitability & quality (026–050) ────────────────────────────────
    gross = _row(fin, "Gross Profit")
    op_inc = _row(fin, "Operating Income")
    net_inc = _row(fin, "Net Income")
    ocf = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    capex = _row(cf, "Capital Expenditure", "Capital Expenditures")
    total_assets = _row(bs, "Total Assets")

    gm = _safe_div(_latest(gross), _latest(rev))
    gm_prev = _safe_div(_prior(gross), _prior(rev))
    om = _safe_div(_latest(op_inc), _latest(rev))
    fcf = None
    if _latest(ocf) is not None and _latest(capex) is not None:
        fcf = _latest(ocf) + _latest(capex)  # capex reported negative
    fcf_conversion = _safe_div(fcf, _latest(net_inc))
    accruals = None
    if _latest(net_inc) is not None and _latest(ocf) is not None and _latest(total_assets):
        accruals = round((_latest(net_inc) - _latest(ocf)) / _latest(total_assets), 4)

    profitability = {
        "gross_margin_pct": round(gm * 100, 2) if gm is not None else None,
        "gross_margin_trend_pp": (
            round((gm - gm_prev) * 100, 2) if gm is not None and gm_prev is not None else None
        ),
        "operating_margin_pct": round(om * 100, 2) if om is not None else None,
        "fcf_musd": round(fcf / 1e6, 1) if fcf is not None else None,
        "fcf_conversion": round(fcf_conversion, 2) if fcf_conversion is not None else None,
        "accruals_ratio": accruals,  # high positive = earnings not backed by cash
        "roe_pct": round(info["returnOnEquity"] * 100, 2) if info.get("returnOnEquity") else None,
    }

    # ── Piotroski F-score (9 tests, deterministic) ───────────────────────
    f_score, f_tests = _piotroski(fin, bs, cf, rev)
    profitability["piotroski_f_score"] = f_score
    profitability["piotroski_components"] = f_tests

    # ── Balance sheet vulnerability (051–075) ────────────────────────────
    total_debt = _row(bs, "Total Debt")
    cash = _row(bs, "Cash And Cash Equivalents", "Cash")
    cur_assets = _row(bs, "Current Assets", "Total Current Assets")
    cur_liab = _row(bs, "Current Liabilities", "Total Current Liabilities")
    ebitda = info.get("ebitda")
    interest = _row(fin, "Interest Expense")

    net_debt = None
    if _latest(total_debt) is not None and _latest(cash) is not None:
        net_debt = _latest(total_debt) - _latest(cash)
    balance_sheet = {
        "net_debt_musd": round(net_debt / 1e6, 1) if net_debt is not None else None,
        "net_debt_to_ebitda": round(_safe_div(net_debt, ebitda), 2) if _safe_div(net_debt, ebitda) is not None else None,
        "current_ratio": round(_safe_div(_latest(cur_assets), _latest(cur_liab)), 2)
            if _safe_div(_latest(cur_assets), _latest(cur_liab)) is not None else None,
        "interest_coverage": round(_safe_div(_latest(op_inc), abs(_latest(interest))), 1)
            if _latest(interest) not in (None, 0) and _latest(op_inc) is not None else None,
        "altman_z": _altman_z(info, fin, bs, rev),
    }

    # ── Valuation & capital allocation (076–100) ─────────────────────────
    mcap = info.get("marketCap")
    ev = info.get("enterpriseValue")
    shares = _row(bs, "Ordinary Shares Number", "Share Issued")
    dilution = _pct_change(_latest(shares), _prior(shares))
    valuation = {
        "pe_trailing": round(info["trailingPE"], 2) if info.get("trailingPE") else None,
        "pe_forward": round(info["forwardPE"], 2) if info.get("forwardPE") else None,
        "peg": round(info["trailingPegRatio"], 2) if info.get("trailingPegRatio") else None,
        "ev_to_ebitda": round(_safe_div(ev, ebitda), 2) if _safe_div(ev, ebitda) is not None else None,
        "ev_to_sales": round(_safe_div(ev, _latest(rev)), 2) if _safe_div(ev, _latest(rev)) is not None else None,
        "fcf_yield_pct": round(_safe_div(fcf, mcap) * 100, 2) if _safe_div(fcf, mcap) is not None else None,
        "dividend_yield_pct": round(info["dividendYield"] * 100, 2) if info.get("dividendYield") else None,
        "share_dilution_yoy_pct": dilution,  # negative = buybacks
        "price_to_book": round(info["priceToBook"], 2) if info.get("priceToBook") else None,
    }

    # ── Earnings & ownership (101–150) ───────────────────────────────────
    earnings_ownership = {
        "analyst_target_mean": info.get("targetMeanPrice"),
        "analyst_recommendation": info.get("recommendationKey"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "held_pct_institutions": round(info["heldPercentInstitutions"] * 100, 2)
            if info.get("heldPercentInstitutions") else None,
        "held_pct_insiders": round(info["heldPercentInsiders"] * 100, 2)
            if info.get("heldPercentInsiders") else None,
        "short_pct_of_float": round(info["shortPercentOfFloat"] * 100, 2)
            if info.get("shortPercentOfFloat") else None,
        "earnings_growth_pct": round(info["earningsGrowth"] * 100, 2)
            if info.get("earningsGrowth") else None,
    }

    result = {
        "symbol": symbol.upper(),
        "as_of": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "groups": {
            "growth": growth,
            "profitability": profitability,
            "balance_sheet": balance_sheet,
            "valuation": valuation,
            "earnings_ownership": earnings_ownership,
        },
        "coverage": _coverage_card(growth, profitability, balance_sheet, valuation, earnings_ownership),
    }
    _CACHE[cache_key] = {"data": result, "ts": time.time()}
    return result


def _piotroski(fin, bs, cf, rev) -> tuple:
    """Piotroski F-score: 9 binary accounting-quality tests."""
    tests = {}
    net_inc = _row(fin, "Net Income")
    ocf = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    total_assets = _row(bs, "Total Assets")
    total_debt = _row(bs, "Total Debt", "Long Term Debt")
    cur_assets = _row(bs, "Current Assets", "Total Current Assets")
    cur_liab = _row(bs, "Current Liabilities", "Total Current Liabilities")
    gross = _row(fin, "Gross Profit")
    shares = _row(bs, "Ordinary Shares Number", "Share Issued")

    roa = _safe_div(_latest(net_inc), _latest(total_assets))
    roa_prev = _safe_div(_prior(net_inc), _prior(total_assets))
    tests["positive_net_income"] = _latest(net_inc) is not None and _latest(net_inc) > 0
    tests["positive_ocf"] = _latest(ocf) is not None and _latest(ocf) > 0
    tests["roa_improving"] = roa is not None and roa_prev is not None and roa > roa_prev
    tests["ocf_exceeds_net_income"] = (
        _latest(ocf) is not None and _latest(net_inc) is not None and _latest(ocf) > _latest(net_inc)
    )
    lev = _safe_div(_latest(total_debt), _latest(total_assets))
    lev_prev = _safe_div(_prior(total_debt), _prior(total_assets))
    tests["leverage_decreasing"] = lev is not None and lev_prev is not None and lev <= lev_prev
    cr = _safe_div(_latest(cur_assets), _latest(cur_liab))
    cr_prev = _safe_div(_prior(cur_assets), _prior(cur_liab))
    tests["current_ratio_improving"] = cr is not None and cr_prev is not None and cr > cr_prev
    tests["no_dilution"] = (
        _latest(shares) is not None and _prior(shares) is not None
        and _latest(shares) <= _prior(shares) * 1.02
    )
    gm = _safe_div(_latest(gross), _latest(rev))
    gm_prev = _safe_div(_prior(gross), _prior(rev))
    tests["gross_margin_improving"] = gm is not None and gm_prev is not None and gm > gm_prev
    at = _safe_div(_latest(rev), _latest(total_assets))
    at_prev = _safe_div(_prior(rev), _prior(total_assets))
    tests["asset_turnover_improving"] = at is not None and at_prev is not None and at > at_prev

    computable = {k: v for k, v in tests.items() if v is not None}
    score = sum(1 for v in computable.values() if v)
    return score, tests


def _altman_z(info, fin, bs, rev) -> Optional[float]:
    """Altman Z-score (manufacturing formula; interpret sector-appropriately)."""
    try:
        ta = _latest(_row(bs, "Total Assets"))
        tl = _latest(_row(bs, "Total Liabilities Net Minority Interest", "Total Liabilities"))
        ca = _latest(_row(bs, "Current Assets", "Total Current Assets"))
        cl = _latest(_row(bs, "Current Liabilities", "Total Current Liabilities"))
        re = _latest(_row(bs, "Retained Earnings"))
        ebit = _latest(_row(fin, "EBIT", "Operating Income"))
        sales = _latest(rev)
        mcap = info.get("marketCap")
        if None in (ta, tl, ca, cl, re, ebit, sales, mcap) or ta == 0 or tl == 0:
            return None
        wc = ca - cl
        z = (1.2 * wc / ta + 1.4 * re / ta + 3.3 * ebit / ta
             + 0.6 * mcap / tl + 1.0 * sales / ta)
        return round(z, 2)
    except Exception:
        return None


def _coverage_card(*groups: Dict) -> Dict[str, Any]:
    """How many metrics were computable vs n/a — honest coverage reporting."""
    total = computed = 0
    for g in groups:
        for k, v in g.items():
            if k == "piotroski_components":
                continue
            total += 1
            if v is not None:
                computed += 1
    return {"metrics_total": total, "metrics_computed": computed,
            "coverage_pct": round(computed / total * 100, 1) if total else 0}
