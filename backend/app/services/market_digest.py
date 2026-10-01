"""
Market Digest Service
─────────────────────
Builds a concise, human-readable digest combining:
  - Market regime + key indices (VIX, S&P, AI Boom index)
  - Upcoming earnings watchlist (next N days)

Formatted for WhatsApp / SMS / email delivery. Always appends the
"not financial advice" disclaimer. Nothing is sent here — the caller
queues it through the consent-based notification service.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DISCLAIMER = "\n\n_AI-generated research, not financial advice._"


def _fmt_cap(n: float) -> str:
    if not n:
        return ""
    if n >= 1e12:
        return f"${n/1e12:.1f}T"
    if n >= 1e9:
        return f"${n/1e9:.1f}B"
    if n >= 1e6:
        return f"${n/1e6:.0f}M"
    return f"${n:,.0f}"


async def build_market_digest(
    earnings_days: int = 14,
    earnings_limit: int = 12,
    watchlist: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Gather market overview + AI boom + upcoming earnings and format a digest.

    Returns {"title", "message", "data"} ready to queue for notification.
    """
    from app.services.earnings_intelligence import get_upcoming_earnings

    try:
        from app.services.market_intelligence import get_market_overview, get_ai_boom_index
        overview_task = get_market_overview()
        ai_boom_task = get_ai_boom_index()
    except Exception:
        overview_task = asyncio.sleep(0, result={})
        ai_boom_task = asyncio.sleep(0, result={})

    earnings_task = get_upcoming_earnings(days=earnings_days, universe=watchlist)

    overview, ai_boom, earnings = await asyncio.gather(
        overview_task, ai_boom_task, earnings_task, return_exceptions=True
    )

    overview = overview if isinstance(overview, dict) else {}
    ai_boom = ai_boom if isinstance(ai_boom, dict) else {}
    earnings = earnings if isinstance(earnings, list) else []

    # ── Market line ──────────────────────────────────────────────────────────
    lines: List[str] = []
    today = datetime.now(timezone.utc).strftime("%a %b %d, %Y")
    lines.append(f"*Avira Market Digest* — {today}")
    lines.append("")

    # Indices / VIX
    indices = overview.get("indices", {}) or overview.get("market_overview", {})
    vix = None
    macro = overview.get("macro", {}) or {}
    try:
        sp = indices.get("^GSPC") or indices.get("sp500") or {}
        vix_obj = macro.get("vix") or indices.get("^VIX") or {}
        if isinstance(vix_obj, dict):
            vix = vix_obj.get("value")
    except Exception:
        pass

    regime = ai_boom.get("regime") or overview.get("regime")
    if regime:
        lines.append(f"📊 Regime: *{regime}*")
    if ai_boom.get("ai_boom_score") is not None:
        lines.append(f"🤖 AI Boom Index: *{ai_boom['ai_boom_score']:.1f}*")
    if vix is not None:
        lines.append(f"😱 VIX: {vix}")

    # Top movers from ai_boom subsectors if available
    subs = ai_boom.get("subsectors") or ai_boom.get("components") or {}
    if isinstance(subs, dict) and subs:
        try:
            ranked = sorted(
                [(k, v.get("change_30d", v.get("avg_change_30d", 0)) if isinstance(v, dict) else 0)
                 for k, v in subs.items()],
                key=lambda x: x[1], reverse=True,
            )
            if ranked:
                top = ranked[0]
                lines.append(f"🔥 Hot sector: {top[0]} ({top[1]:+.1f}%/30d)")
        except Exception:
            pass

    # ── Earnings watchlist ─────────────────────────────────────────────────────
    lines.append("")
    lines.append(f"*📅 Earnings to watch (next {earnings_days}d):*")
    if not earnings:
        lines.append("_None in this window. Try a longer horizon._")
    else:
        for e in earnings[:earnings_limit]:
            rec = (e.get("recommendation") or "").upper()
            rec_tag = f" · {rec}" if rec and rec not in ("NONE", "") else ""
            cap = _fmt_cap(e.get("market_cap", 0))
            cap_tag = f" · {cap}" if cap else ""
            lines.append(
                f"• {e['earnings_date']} *{e['symbol']}* "
                f"({e.get('earnings_time','')}){cap_tag}{rec_tag}"
            )

    message = "\n".join(lines) + DISCLAIMER

    return {
        "title": f"Market Digest — {today}",
        "message": message,
        "data": {
            "regime": regime,
            "ai_boom_score": ai_boom.get("ai_boom_score"),
            "vix": vix,
            "earnings_count": len(earnings),
            "earnings": earnings[:earnings_limit],
        },
    }


async def build_earnings_watchlist_digest(
    symbols: List[str],
    days: int = 30,
) -> Dict[str, Any]:
    """Digest for a specific user-provided watchlist of symbols."""
    from app.services.earnings_intelligence import get_upcoming_earnings

    earnings = await get_upcoming_earnings(days=days, universe=symbols)
    today = datetime.now(timezone.utc).strftime("%a %b %d, %Y")

    lines = [f"*Avira Earnings Watch* — {today}", ""]
    if not earnings:
        lines.append(f"_No earnings for your {len(symbols)} symbols in the next {days}d._")
    else:
        for e in earnings:
            rec = (e.get("recommendation") or "").upper()
            rec_tag = f" · {rec}" if rec and rec != "NONE" else ""
            price = e.get("price")
            price_tag = f" · ${price:.2f}" if price else ""
            lines.append(
                f"• {e['earnings_date']} *{e['symbol']}* "
                f"({e.get('earnings_time','')}){price_tag}{rec_tag}"
            )

    message = "\n".join(lines) + DISCLAIMER
    return {
        "title": f"Earnings Watch — {today}",
        "message": message,
        "data": {"symbols": symbols, "earnings": earnings},
    }
