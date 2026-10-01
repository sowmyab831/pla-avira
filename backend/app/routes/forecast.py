"""
Forecast routes:
  - /api/forecast/day-trade/{symbol}   intraday plan (15-min default)
  - /api/forecast/long-term/{symbol}   30/90/180-day trend + swing plan
  - /api/forecast/combined/{symbol}    both in one call
  - /api/forecast/explain/{symbol}     LLM-narrated trade brief (qwen2.5:14b)
  - /api/forecast/models-used          which LLMs / ML models the app uses
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.middleware.subscription_gate import soft_rate_limit

from app.services.llm_client import extract_json, generate
from app.services.forecasting import (
    forecast_combined,
    forecast_day_trade,
    forecast_long_term,
)

router = APIRouter(prefix="/api/forecast", tags=["forecast"])
logger = logging.getLogger(__name__)

VALID_INTERVALS = {"1m", "5m", "15m", "30m", "60m", "1h"}


@router.get("/day-trade/{symbol}")
async def day_trade(symbol: str, interval: str = Query("15m")):
    if interval not in VALID_INTERVALS:
        interval = "15m"
    return await forecast_day_trade(symbol, interval=interval)


@router.get("/long-term/{symbol}", dependencies=[Depends(soft_rate_limit("forecast"))])
async def long_term(symbol: str):
    return await forecast_long_term(symbol)


@router.get("/combined/{symbol}", dependencies=[Depends(soft_rate_limit("forecast"))])
async def combined(symbol: str, interval: str = Query("15m")):
    if interval not in VALID_INTERVALS:
        interval = "15m"
    return await forecast_combined(symbol, interval=interval)


@router.get("/explain/{symbol}", dependencies=[Depends(soft_rate_limit("forecast"))])
async def explain(
    symbol: str,
    scope: str = Query("combined", pattern="^(day_trade|long_term|combined)$"),
):
    """LLM-narrated trade brief. Explains the model stack in plain English."""
    from app.config import settings

    if scope == "day_trade":
        data = await forecast_day_trade(symbol)
    elif scope == "long_term":
        data = await forecast_long_term(symbol)
    else:
        data = await forecast_combined(symbol)

    compact = json.dumps(data)[:8000]
    model = settings.model_for_task("finance")

    prompt = (
        "You are AVIRA's trading analyst. The user has a forecast payload below. "
        "Return STRICT JSON with keys:\n"
        "  summary          : <=200 chars plain-English recap\n"
        "  bull_case        : 2 sentences\n"
        "  bear_case        : 2 sentences\n"
        "  trade_plan       : { action, entry, stop, target_1, target_2, position_size_pct }\n"
        "  confidence_label : one of 'very_low','low','medium','high','very_high'\n"
        "  disclaimer       : short compliance note\n"
        "No prose outside the JSON.\n\n"
        f"FORECAST:\n{compact}"
    )

    try:
        text = await generate(
            prompt, task="finance", temperature=0.25,
            max_tokens=700, json_mode=True, timeout=settings.ollama_timeout,
        )
        if not text:
            raise RuntimeError("LLM unavailable or empty response")
        brief = extract_json(text)
        if not isinstance(brief, dict):
            brief = {"raw": text}
    except Exception as e:
        logger.warning("forecast explain LLM failed: %s", e)
        return {
            "symbol": symbol.upper(),
            "scope": scope,
            "llm_error": str(e),
            "fallback_brief": {
                "summary": (data.get("rationale") or "forecast available"),
                "confidence_label": "medium",
                "disclaimer": "Statistical forecast only — not financial advice.",
            },
            "data": data,
            "llm_used": {"model": model, "available": False},
        }

    return {
        "symbol": symbol.upper(),
        "scope": scope,
        "brief": brief,
        "llm_used": {
            "model": model,
            "provider": "ollama_local",
            "host": settings.ollama_host,
            "temperature": 0.25,
            "private": True,
        },
        "data": data,
    }


@router.get("/models-used")
async def models_used():
    """Transparency endpoint — enumerates every model AVIRA uses, and for what.
    The frontend renders this as a 'Model Stack' panel."""
    from app.config import settings

    return {
        "llms": [
            {
                "role": "finance_reasoner",
                "model": settings.ollama_finance_model,
                "provider": "ollama (local)",
                "used_for": [
                    "/api/market-intel/synthesis",
                    "/api/forecast/explain/*",
                    "stock analysis, earnings synthesis, portfolio reasoning",
                ],
                "private": True,
                "approx_ram_gb": 9.3,
            },
            {
                "role": "fast_assistant",
                "model": settings.ollama_fast_model,
                "provider": "ollama (local)",
                "used_for": [
                    "/api/assistant/chat",
                    "email extraction, shopping/travel queries, calendar parsing",
                ],
                "private": True,
                "approx_ram_gb": 4.4,
            },
            {
                "role": "deep_reasoner",
                "model": settings.ollama_deep_model,
                "provider": "ollama (local)",
                "used_for": ["/api/deep-analysis (on-demand)"],
                "private": True,
                "approx_ram_gb": 20.0,
            },
            {
                "role": "embeddings",
                "model": "nomic-embed-text",
                "provider": "ollama (local)",
                "used_for": ["RAG, vector search via Qdrant"],
                "private": True,
                "approx_ram_gb": 0.3,
            },
        ],
        "ml_models": [
            {
                "role": "direction_predictor",
                "model": "xgboost_2y",
                "used_for": [
                    "per-ticker next-day direction probability",
                    "long-term forecast drift tilt",
                ],
                "trained_on": "2y daily OHLCV + 18 indicator features",
                "store": "meridian/research/models/*.pkl",
            },
            {
                "role": "statistical_forecaster",
                "model": "ewma_drift + ar1",
                "used_for": ["intraday day-trade forecast path"],
                "trained_on": "recent intraday returns (rolling)",
            },
        ],
        "data_sources": {
            "prices": ["yfinance (Yahoo)"],
            "news": ["Reuters", "BBC", "Bloomberg", "Yahoo Finance", "Ars Technica",
                     "MIT Tech Review", "Hacker News", "TechCrunch", "FDA", "Nature",
                     "ScienceDaily", "ArXiv cs.AI"],
            "geopolitics": ["Reuters World", "BBC World", "Al Jazeera", "Defense News"],
            "social_sentiment": ["Reddit (WSB, stocks, investing)", "Truth Social RSS"],
            "filings": ["SEC EDGAR (4, 13F-HR, 8-K, 10-K, 10-Q, SC 13D/G)"],
            "commodities": ["Mining.com", "OilPrice", "Rigzone", "Reuters Commodities"],
        },
        "compute_profile": {
            "target_hardware": "Apple Silicon M4 16GB unified memory",
            "gpu_budget_gb": 11,
            "models_under_budget": [settings.ollama_finance_model, settings.ollama_fast_model, "nomic-embed-text"],
            "models_partial_gpu": [settings.ollama_deep_model],
            "ml_runtime": "XGBoost (CPU, hist tree_method)",
            "privacy": "All LLM inference + ML stays on-device by default. External LLMs disabled unless API keys set.",
        },
    }
