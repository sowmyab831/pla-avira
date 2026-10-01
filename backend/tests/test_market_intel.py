"""
Smoke + structural tests for the market intelligence service.

These tests exercise the actual aggregator (no heavy mocking) but tolerate
upstream rate-limits / outages by accepting an `error` field. The point is to
guarantee:
  * shape of every endpoint payload is what the frontend expects
  * the service never raises an unhandled exception
  * caching works
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from app.services.market_intelligence import (
    AI_BOOM_UNIVERSE,
    INFLUENCERS,
    _CACHE,
    _cache_get,
    _cache_set,
    get_ai_boom_index,
    get_big_money_flow,
    get_full_intelligence_snapshot,
    get_geopolitics,
    get_influencer_signals,
    get_market_overview,
    get_resource_discoveries,
    get_sec_recent_filings,
    get_tech_breakthroughs,
)


def _has_keys(d: Dict[str, Any], keys: list[str]) -> bool:
    return all(k in d for k in keys)


# ─── universe data sanity ───────────────────────────────────────────────────

def test_ai_boom_universe_is_well_formed():
    assert "compute_chips" in AI_BOOM_UNIVERSE
    assert "rare_earth_miners" in AI_BOOM_UNIVERSE
    # All tickers are uppercase strings
    for cat, syms in AI_BOOM_UNIVERSE.items():
        assert isinstance(syms, list) and len(syms) >= 3, cat
        for s in syms:
            assert s.isupper() and 1 <= len(s) <= 6


def test_influencers_registry_complete():
    assert len(INFLUENCERS) >= 12
    for p in INFLUENCERS:
        for key in ("handle", "name", "category"):
            assert key in p, p
    # At least one influencer should have a direct RSS source (Trump's Truth Social).
    assert any("rss" in p for p in INFLUENCERS)


# ─── cache primitives ───────────────────────────────────────────────────────

def test_cache_roundtrip():
    _CACHE.clear()
    _cache_set("k", {"v": 1})
    assert _cache_get("k", ttl=60) == {"v": 1}
    # ttl=0 should treat as expired
    assert _cache_get("k", ttl=0) is None


# ─── async aggregator smoke tests (network) ─────────────────────────────────

@pytest.mark.asyncio
async def test_market_overview_shape():
    ov = await get_market_overview()
    assert _has_keys(ov, ["timestamp", "indices", "macro", "sectors"])
    # Indices may be partial under rate-limits but the shape must hold
    assert isinstance(ov["indices"], dict)
    assert isinstance(ov["sectors"], dict)


@pytest.mark.asyncio
async def test_ai_boom_index_shape():
    ai = await get_ai_boom_index()
    assert _has_keys(ai, ["ai_boom_score", "regime", "categories", "leaders", "laggards"])
    assert ai["regime"] in {
        "blow-off-top", "expansion", "stable", "cooling", "correction"
    }
    if ai["categories"]:
        first_cat = next(iter(ai["categories"].values()))
        assert _has_keys(first_cat, ["avg_30d_pct", "avg_90d_pct", "tickers"])


@pytest.mark.asyncio
async def test_geopolitics_shape():
    g = await get_geopolitics()
    assert _has_keys(g, ["items", "headline_count", "risk_level"])
    assert g["risk_level"] in {"calm", "moderate", "elevated", "unknown"}


@pytest.mark.asyncio
async def test_influencer_signals_shape():
    inf = await get_influencer_signals(limit_per=2)
    assert _has_keys(inf, ["count", "influencers"])
    if inf["influencers"]:
        p = inf["influencers"][0]
        assert _has_keys(p, ["handle", "name", "signal", "avg_sentiment", "items"])
        assert p["signal"] in {"bullish", "bearish", "neutral"}


@pytest.mark.asyncio
async def test_big_money_flow_shape():
    bm = await get_big_money_flow()
    assert _has_keys(bm, ["summary", "insider_form4", "institutional_13f", "activist_13d_13g"])
    s = bm["summary"]
    assert _has_keys(s, ["insider_filings_24h", "institutional_filings_24h", "activist_filings_24h"])


@pytest.mark.asyncio
async def test_sec_filings_shape():
    sec = await get_sec_recent_filings(form_types=["8-K"])
    assert "by_form" in sec and "8-K" in sec["by_form"]


@pytest.mark.asyncio
async def test_tech_breakthroughs_shape():
    tech = await get_tech_breakthroughs()
    assert _has_keys(tech, ["items", "count", "timestamp"])


@pytest.mark.asyncio
async def test_resource_discoveries_shape():
    res = await get_resource_discoveries()
    assert _has_keys(res, ["items", "count"])


@pytest.mark.asyncio
async def test_full_snapshot_bundle():
    snap = await get_full_intelligence_snapshot()
    assert _has_keys(
        snap,
        [
            "timestamp",
            "market_overview",
            "ai_boom",
            "influencers",
            "geopolitics",
            "tech_breakthroughs",
            "resource_discoveries",
            "big_money_flow",
        ],
    )
