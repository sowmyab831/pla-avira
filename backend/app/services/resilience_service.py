"""
Geopolitical Resilience Scoring Service.

Scores stocks 1-10 based on geopolitical risk factors:
- Tariff exposure
- Geographic revenue concentration
- Supply chain complexity
- Energy cost sensitivity

Auto-actions:
- Score < 5 → Auto-tighten stop-loss to 3%
- Score drops >2 points → Alert user
- Policy shock detected → Update all affected stocks
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Sector classifications for risk scoring
TARIFF_SENSITIVE_SECTORS = {
    "steel", "aluminum", "semiconductors", "automotive", "chemicals",
    "solar", "electronics", "textiles", "agriculture",
}

ENERGY_INTENSIVE_SECTORS = {
    "airlines", "chemicals", "steel", "mining", "manufacturing",
    "shipping", "trucking", "utilities",
}

# Known company profiles for scoring
COMPANY_PROFILES = {
    "AAPL": {"sector": "technology", "china_revenue_pct": 19, "supply_chain": {"single_source": True, "countries": ["China", "Taiwan", "India"]}, "description": "Apple Inc"},
    "TSLA": {"sector": "automotive", "china_revenue_pct": 22, "supply_chain": {"single_source": False, "countries": ["China", "USA", "Germany"]}, "description": "Tesla Inc"},
    "NVDA": {"sector": "semiconductors", "china_revenue_pct": 17, "supply_chain": {"single_source": True, "countries": ["Taiwan"]}, "description": "NVIDIA Corp"},
    "MSFT": {"sector": "technology", "china_revenue_pct": 3, "supply_chain": {"single_source": False, "countries": ["USA"]}, "description": "Microsoft Corp"},
    "GOOGL": {"sector": "technology", "china_revenue_pct": 2, "supply_chain": {"single_source": False, "countries": ["USA"]}, "description": "Alphabet Inc"},
    "AMZN": {"sector": "retail", "china_revenue_pct": 1, "supply_chain": {"single_source": False, "countries": ["USA", "Global"]}, "description": "Amazon.com Inc"},
    "META": {"sector": "technology", "china_revenue_pct": 0, "supply_chain": {"single_source": False, "countries": ["USA"]}, "description": "Meta Platforms Inc"},
    "RELIANCE.NS": {"sector": "conglomerate", "china_revenue_pct": 2, "supply_chain": {"single_source": False, "countries": ["India"]}, "description": "Reliance Industries"},
    "TCS.NS": {"sector": "it_services", "china_revenue_pct": 0, "supply_chain": {"single_source": False, "countries": ["India", "USA", "UK"]}, "description": "Tata Consultancy Services"},
    "INFY.NS": {"sector": "it_services", "china_revenue_pct": 0, "supply_chain": {"single_source": False, "countries": ["India", "USA"]}, "description": "Infosys Ltd"},
}

# In-memory cache for resilience scores
_resilience_cache: Dict[str, Dict[str, Any]] = {}
_alerts: List[Dict[str, Any]] = []


class ResilienceService:
    """
    Geopolitical resilience scoring for portfolio stocks.
    """

    def score_stock(self, symbol: str, profile: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Calculate resilience score for a stock (1-10 scale).

        Scoring: Start at 10, subtract for risk factors.
        """
        if profile is None:
            profile = COMPANY_PROFILES.get(symbol.upper(), {})

        sector = profile.get("sector", "unknown").lower()
        china_pct = profile.get("china_revenue_pct", 0)
        supply = profile.get("supply_chain", {})

        score = 10.0
        factors = []

        # Factor 1: Tariff exposure (-2 for sensitive sectors)
        if sector in TARIFF_SENSITIVE_SECTORS:
            score -= 2.0
            factors.append({
                "factor": "tariff_exposure",
                "impact": -2.0,
                "reason": f"{sector.title()} is tariff-sensitive",
            })

        # Factor 2: Geographic concentration (-2 if >30% from high-risk country)
        high_risk_countries = {"china", "russia", "taiwan", "iran"}
        revenue_geo = {}
        if china_pct > 0:
            revenue_geo["China"] = china_pct

        for country, pct in revenue_geo.items():
            if pct > 30 and country.lower() in high_risk_countries:
                score -= 2.0
                factors.append({
                    "factor": "geographic_concentration",
                    "impact": -2.0,
                    "reason": f"{pct}% revenue from {country} (>30% threshold)",
                })
            elif pct > 15 and country.lower() in high_risk_countries:
                score -= 1.0
                factors.append({
                    "factor": "geographic_exposure",
                    "impact": -1.0,
                    "reason": f"{pct}% revenue from {country}",
                })

        # Factor 3: Supply chain risk (-1 for single-source components)
        if supply.get("single_source"):
            score -= 1.0
            factors.append({
                "factor": "supply_chain_risk",
                "impact": -1.0,
                "reason": "Single-source critical components",
            })

        supply_countries = supply.get("countries", [])
        if any(c.lower() in high_risk_countries for c in supply_countries):
            score -= 0.5
            factors.append({
                "factor": "supply_chain_geography",
                "impact": -0.5,
                "reason": f"Supply chain in high-risk countries: {', '.join(supply_countries)}",
            })

        # Factor 4: Energy cost sensitivity (-1 for energy-intensive sectors)
        if sector in ENERGY_INTENSIVE_SECTORS:
            score -= 1.0
            factors.append({
                "factor": "energy_sensitivity",
                "impact": -1.0,
                "reason": f"{sector.title()} is energy cost sensitive",
            })

        score = max(1.0, min(10.0, score))

        # Determine risk level
        if score >= 8:
            risk_level = "low"
        elif score >= 6:
            risk_level = "moderate"
        elif score >= 4:
            risk_level = "elevated"
        else:
            risk_level = "high"

        # Auto-actions
        auto_actions = []
        if score < 5:
            auto_actions.append("⚠️ Auto-tighten stop-loss to 3%")
            auto_actions.append("📊 Increase monitoring frequency to hourly")
        if score < 3:
            auto_actions.append("🚨 Consider reducing position by 50%")
            auto_actions.append("🔔 Set price alert for -5% move")

        result = {
            "symbol": symbol.upper(),
            "resilience_score": round(score, 1),
            "max_score": 10,
            "risk_level": risk_level,
            "sector": sector,
            "factors": factors,
            "auto_actions": auto_actions,
            "description": profile.get("description", ""),
            "scored_at": datetime.now().isoformat(),
        }

        # Cache and check for alerts
        previous = _resilience_cache.get(symbol.upper())
        _resilience_cache[symbol.upper()] = result

        if previous:
            prev_score = previous.get("resilience_score", 10)
            drop = prev_score - score
            if drop >= 2:
                alert = {
                    "type": "resilience_drop",
                    "symbol": symbol.upper(),
                    "previous_score": prev_score,
                    "new_score": score,
                    "drop": round(drop, 1),
                    "message": f"⚠️ {symbol.upper()} resilience dropped {drop:.1f} points ({prev_score} → {score})",
                    "timestamp": datetime.now().isoformat(),
                }
                _alerts.append(alert)
                result["alert"] = alert

        return result

    def score_portfolio(self, symbols: List[str]) -> Dict[str, Any]:
        """Score all stocks in a portfolio."""
        scores = []
        for symbol in symbols:
            scores.append(self.score_stock(symbol))

        avg_score = sum(s["resilience_score"] for s in scores) / len(scores) if scores else 0
        weakest = min(scores, key=lambda s: s["resilience_score"]) if scores else None
        strongest = max(scores, key=lambda s: s["resilience_score"]) if scores else None

        return {
            "portfolio_resilience": round(avg_score, 1),
            "stock_count": len(scores),
            "risk_level": "low" if avg_score >= 7 else "moderate" if avg_score >= 5 else "high",
            "scores": scores,
            "weakest_link": weakest,
            "strongest": strongest,
            "high_risk_count": sum(1 for s in scores if s["resilience_score"] < 5),
        }

    def get_alerts(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get resilience alerts, optionally filtered by symbol."""
        if symbol:
            return [a for a in _alerts if a.get("symbol") == symbol.upper()]
        return _alerts

    def get_cached_score(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached resilience score for a symbol."""
        return _resilience_cache.get(symbol.upper())


# Singleton
_resilience_service: Optional[ResilienceService] = None


def get_resilience_service() -> ResilienceService:
    global _resilience_service
    if _resilience_service is None:
        _resilience_service = ResilienceService()
    return _resilience_service
