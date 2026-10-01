"""
Market Intelligence routes.

Wires the aggregator in app.services.market_intelligence to FastAPI and adds
an LLM synthesis endpoint that asks the local finance model (qwen2.5:14b)
to read the snapshot and return a prioritized, explainable trade view.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.llm_client import extract_json, generate
from app.services.market_intelligence import (
    get_ai_boom_index,
    get_big_money_flow,
    get_earnings_adherence,
    get_full_intelligence_snapshot,
    get_geopolitics,
    get_influencer_signals,
    get_market_overview,
    get_resource_discoveries,
    get_sec_recent_filings,
    get_tech_breakthroughs,
)

router = APIRouter(prefix="/api/market-intel", tags=["market-intel"])
logger = logging.getLogger(__name__)


@router.get("/overview")
async def overview():
    return await get_market_overview()


@router.get("/ai-boom")
async def ai_boom():
    return await get_ai_boom_index()


@router.get("/influencers")
async def influencers(limit_per: int = Query(5, ge=1, le=15)):
    return await get_influencer_signals(limit_per=limit_per)


@router.get("/geopolitics")
async def geopolitics():
    return await get_geopolitics()


@router.get("/big-money")
async def big_money():
    return await get_big_money_flow()


@router.get("/sec-filings")
async def sec_filings(forms: Optional[str] = Query(None, description="comma-separated form types")):
    types = [f.strip() for f in forms.split(",")] if forms else None
    return await get_sec_recent_filings(form_types=types)


@router.get("/tech-breakthroughs")
async def tech_breakthroughs():
    return await get_tech_breakthroughs()


@router.get("/resources")
async def resources():
    return await get_resource_discoveries()


@router.get("/earnings/{symbol}")
async def earnings(symbol: str, years: int = Query(5, ge=1, le=10)):
    return await get_earnings_adherence(symbol, years=years)


@router.get("/snapshot")
async def snapshot():
    """One-shot endpoint feeding the dashboard's 'General' tab."""
    return await get_full_intelligence_snapshot()


# ─────────────────────────────────────────────────────────────────────────────
# LLM synthesis: turn the snapshot into a prioritized, explainable view.
# Uses the local Ollama finance model (qwen2.5:14b by default).
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/synthesis")
async def synthesis(focus: str = Query("general", pattern="^(general|ai_boom|day_trading)$")):
    from app.config import settings

    snapshot_data = await get_full_intelligence_snapshot()

    # Trim payload to keep prompt lean — LLM doesn't need every headline.
    compact = {
        "as_of": snapshot_data["timestamp"],
        "market_overview": snapshot_data.get("market_overview", {}),
        "ai_boom": {
            k: v for k, v in (snapshot_data.get("ai_boom") or {}).items()
            if k in ("ai_boom_score", "regime", "overall_avg_30d_pct", "overall_avg_90d_pct", "leaders", "laggards")
        },
        "geopolitics_risk": (snapshot_data.get("geopolitics") or {}).get("risk_level"),
        "top_influencer_signals": [
            {"name": p["name"], "signal": p["signal"], "avg_sentiment": p["avg_sentiment"],
             "headline": p["items"][0]["title"] if p.get("items") else ""}
            for p in (snapshot_data.get("influencers") or {}).get("influencers", [])[:8]
        ],
        "big_money_summary": (snapshot_data.get("big_money_flow") or {}).get("summary"),
        "tech_top": [it["title"] for it in (snapshot_data.get("tech_breakthroughs") or {}).get("items", [])[:8]],
        "geopol_top": [it["title"] for it in (snapshot_data.get("geopolitics") or {}).get("items", [])[:8]],
    }

    focus_directive = {
        "general":      "Provide a balanced, multi-asset daily intelligence brief.",
        "ai_boom":      "Focus the brief on the AI compute / energy / chips / cloud / data stack.",
        "day_trading": "Focus on intraday-relevant setups, catalysts, and momentum names for today.",
    }[focus]

    prompt = (
        "You are AVIRA's senior market strategist. Read the JSON snapshot of "
        "real-time market intelligence and return a prioritized, explainable "
        "JSON brief.\n\n"
        f"FOCUS: {focus_directive}\n\n"
        "Required output JSON keys:\n"
        "  market_regime           : 'risk-on' | 'risk-off' | 'mixed'\n"
        "  one_line_summary        : <=180 chars\n"
        "  top_3_themes            : array of {theme, why_it_matters, evidence}\n"
        "  bullish_setups          : array of {symbol, thesis, catalysts, risk}\n"
        "  bearish_setups          : array of {symbol, thesis, catalysts, risk}\n"
        "  watch_today             : array of symbols\n"
        "  risk_warnings           : array of strings\n"
        "  ai_boom_view            : { score_interpretation, leaders, laggards, near_term_view }\n"
        "Return ONLY valid JSON — no prose before or after.\n\n"
        "SNAPSHOT:\n"
        f"{json.dumps(compact)[:14000]}"
    )

    model = settings.model_for_task("finance")

    try:
        text = await generate(
            prompt, task="finance", temperature=0.3,
            max_tokens=1400, json_mode=True, timeout=settings.ollama_timeout,
        )
        if not text:
            raise RuntimeError("LLM unavailable or empty response")
        brief = extract_json(text)
        if not isinstance(brief, dict):
            brief = {"raw": text}
    except Exception as e:
        logger.warning("LLM synthesis failed: %s", e)
        return {
            "focus": focus,
            "as_of": snapshot_data["timestamp"],
            "llm_error": str(e),
            "fallback_brief": {
                "market_regime": "mixed",
                "one_line_summary": (
                    f"AI Boom score {compact['ai_boom'].get('ai_boom_score')} "
                    f"({compact['ai_boom'].get('regime')}); geopolitics {compact['geopolitics_risk']}."
                ),
                "watch_today": [x["symbol"] for x in (compact["ai_boom"].get("leaders") or [])[:5]],
            },
        }

    return {
        "focus": focus,
        "as_of": snapshot_data["timestamp"],
        "model": model,
        "brief": brief,
        "compact_input": compact,
    }
