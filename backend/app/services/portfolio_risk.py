"""
Portfolio Risk Analyzer
───────────────────────
Analyses portfolio for concentration risk, sector exposure, correlation,
volatility, drawdown risk, and provides diversification suggestions.
"""
from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def analyze_portfolio_risk(holdings: List[Dict]) -> Dict[str, Any]:
    """
    Comprehensive risk analysis for a portfolio.

    holdings: [{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}, ...]
    """
    try:
        import yfinance as yf
        import numpy as np

        if not holdings:
            return {"error": "No holdings to analyze"}

        # Fetch current data for all holdings
        enriched = []
        total_value = 0.0

        for h in holdings:
            sym = h.get("symbol", "").upper()
            shares = float(h.get("shares", 0))
            avg_cost = float(h.get("avg_cost", 0))
            if not sym or shares <= 0:
                continue

            try:
                t = yf.Ticker(sym)
                info = t.info or {}
                price = info.get("currentPrice", info.get("regularMarketPrice", avg_cost))
                current_value = price * shares
                total_value += current_value

                hist = t.history(period="6mo")
                daily_returns = hist["Close"].pct_change().dropna().values if not hist.empty else []

                enriched.append({
                    "symbol": sym,
                    "shares": shares,
                    "avg_cost": avg_cost,
                    "current_price": price,
                    "current_value": current_value,
                    "pnl": (price - avg_cost) * shares,
                    "pnl_pct": ((price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0,
                    "sector": info.get("sector", "Unknown"),
                    "industry": info.get("industry", "Unknown"),
                    "market_cap": info.get("marketCap", 0),
                    "beta": info.get("beta", 1.0),
                    "pe_ratio": info.get("trailingPE", 0),
                    "dividend_yield": info.get("dividendYield", 0),
                    "daily_returns": daily_returns.tolist() if len(daily_returns) > 0 else [],
                    "volatility_annualized": float(np.std(daily_returns) * np.sqrt(252) * 100) if len(daily_returns) > 10 else 0,
                })
            except Exception as e:
                logger.debug(f"Risk data for {sym}: {e}")
                enriched.append({"symbol": sym, "shares": shares, "error": str(e)})

        if total_value == 0:
            return {"error": "Could not calculate portfolio value"}

        # 1. Concentration Risk
        concentration = []
        for h in enriched:
            if "current_value" in h:
                weight = h["current_value"] / total_value * 100
                h["weight_pct"] = round(weight, 2)
                concentration.append({"symbol": h["symbol"], "weight": round(weight, 2)})

        concentration.sort(key=lambda x: x["weight"], reverse=True)
        top_3_weight = sum(c["weight"] for c in concentration[:3])
        concentration_risk = "high" if top_3_weight > 60 else "medium" if top_3_weight > 40 else "low"

        # 2. Sector Exposure
        sector_weights: Dict[str, float] = {}
        for h in enriched:
            if "sector" in h and "weight_pct" in h:
                sector = h["sector"]
                sector_weights[sector] = sector_weights.get(sector, 0) + h["weight_pct"]

        sector_exposure = [{"sector": k, "weight": round(v, 2)} for k, v in sorted(sector_weights.items(), key=lambda x: -x[1])]
        dominant_sector_pct = max(sector_weights.values()) if sector_weights else 0
        sector_risk = "high" if dominant_sector_pct > 50 else "medium" if dominant_sector_pct > 30 else "low"

        # 3. Portfolio Beta
        weighted_beta = sum(
            h.get("beta", 1.0) * h.get("weight_pct", 0) / 100
            for h in enriched if "weight_pct" in h
        )

        # 4. Portfolio Volatility (simple weighted average)
        weighted_vol = sum(
            h.get("volatility_annualized", 0) * h.get("weight_pct", 0) / 100
            for h in enriched if "weight_pct" in h
        )

        # 5. Value at Risk (95% confidence, 1-day)
        portfolio_daily_vol = weighted_vol / (252 ** 0.5)
        var_95 = total_value * (portfolio_daily_vol / 100) * 1.645
        var_99 = total_value * (portfolio_daily_vol / 100) * 2.326

        # 6. Max Drawdown Risk assessment
        dd_risk = "high" if weighted_vol > 30 else "medium" if weighted_vol > 18 else "low"

        # 7. Diversification suggestions
        suggestions = []
        if concentration_risk == "high":
            suggestions.append(f"Top 3 holdings make up {top_3_weight:.0f}% — consider rebalancing")
        if sector_risk == "high":
            dominant = sector_exposure[0] if sector_exposure else {"sector": "Unknown"}
            suggestions.append(f"{dominant['sector']} is {dominant_sector_pct:.0f}% of portfolio — add other sectors")
        if weighted_beta > 1.3:
            suggestions.append(f"Portfolio beta {weighted_beta:.2f} is aggressive — consider adding defensive stocks (utilities, staples)")
        if weighted_beta < 0.7:
            suggestions.append(f"Portfolio beta {weighted_beta:.2f} is defensive — may underperform in bull markets")
        if len(enriched) < 5:
            suggestions.append("Fewer than 5 positions — diversification is limited")
        if len(sector_weights) < 3:
            suggestions.append("Concentrated in fewer than 3 sectors — spread across more industries")
        if not suggestions:
            suggestions.append("Portfolio looks well-diversified across sectors and positions")

        # 8. Risk Score (0-100)
        risk_score = min(100, max(0, int(
            (top_3_weight * 0.3) +
            (dominant_sector_pct * 0.2) +
            (weighted_beta * 15) +
            (weighted_vol * 0.5)
        )))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_value": round(total_value, 2),
            "total_pnl": round(sum(h.get("pnl", 0) for h in enriched), 2),
            "num_positions": len(enriched),
            "risk_score": risk_score,
            "risk_level": "high" if risk_score > 65 else "medium" if risk_score > 40 else "low",
            "portfolio_beta": round(weighted_beta, 3),
            "portfolio_volatility_annualized": round(weighted_vol, 2),
            "var_95_1day": round(var_95, 2),
            "var_99_1day": round(var_99, 2),
            "concentration": {
                "risk": concentration_risk,
                "top_3_weight_pct": round(top_3_weight, 1),
                "breakdown": concentration,
            },
            "sector_exposure": {
                "risk": sector_risk,
                "dominant_sector_pct": round(dominant_sector_pct, 1),
                "breakdown": sector_exposure,
            },
            "drawdown_risk": dd_risk,
            "suggestions": suggestions,
            "holdings": [{k: v for k, v in h.items() if k != "daily_returns"} for h in enriched],
        }
    except Exception as e:
        logger.error(f"Portfolio risk analysis: {e}")
        return {"error": str(e)}
