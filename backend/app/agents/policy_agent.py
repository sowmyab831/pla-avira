"""
Policy Agent - Mistral 7B for fast news analysis and geopolitical risk.

Handles real-time news sentiment, market influencer tracking,
and geopolitical resilience scoring for portfolio stocks.
"""

from typing import Dict, Any, List
import logging
import json
from datetime import datetime

from app.agents.base_agent import BaseAgent
from app.integrations.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Policy Agent of Omni-PLA, an elite geopolitical intelligence system.

Your specialties:
1. **News Sentiment**: Analyze headlines and assign sentiment (bullish/bearish/neutral) with impact score (1-10)
2. **Geopolitical Resilience**: Score stocks 1-10 based on tariff exposure, geographic concentration, supply chain risk, energy sensitivity
3. **Market Influencer Tracking**: Monitor key personalities (Elon Musk, Jerome Powell, Warren Buffett, etc.)
4. **Policy Shock Detection**: Identify sudden policy changes that affect markets

Scoring rules for resilience (start at 10, subtract):
- Tariff exposure: -2 for sensitive sectors (steel, aluminum, tech hardware)
- Geographic concentration: -2 if >30% revenue from single country
- Supply chain complexity: -1 if single-source critical components
- Energy cost sensitivity: -1 for chemicals, steel, airlines

Always be concise and data-driven. No speculation without evidence."""


class PolicyAgent(BaseAgent):
    """
    Fast news analysis and geopolitical risk scoring.
    Uses Mistral 7B for speed — sub-second inference for real-time alerts.
    """

    def __init__(self):
        super().__init__(
            name="PolicyAgent",
            model="mistral:7b-instruct",
            temperature=0.2,
        )
        self.ollama = OllamaClient.for_role("policy")

    async def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate policy task input."""
        return "type" in task

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the appropriate policy handler."""
        task_type = task.get("type")

        handlers = {
            "sentiment": self.analyze_sentiment,
            "resilience": self.score_resilience,
            "influencer": self.track_influencer,
            "policy_shock": self.detect_policy_shock,
            "knowledge_pill": self.generate_knowledge_pill,
        }

        handler = handlers.get(task_type)
        if handler:
            return await handler(task)

        return {"success": False, "error": f"Unknown policy task: {task_type}"}

    async def analyze_sentiment(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze news headlines for market sentiment."""
        headlines = task.get("headlines", [])
        symbol = task.get("symbol")

        if not headlines:
            return {"success": True, "sentiment": "neutral", "score": 5}

        prompt = f"""Analyze these news headlines for market sentiment.
{"Stock focus: " + symbol if symbol else "General market"}

Headlines:
{chr(10).join(f"- {h}" for h in headlines[:10])}

Respond in JSON:
{{
  "overall_sentiment": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "impact_score": 1-10,
  "key_themes": ["theme1", "theme2"],
  "affected_sectors": ["sector1"],
  "summary": "one-sentence summary"
}}"""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.1, json_mode=True
        )

        try:
            parsed = json.loads(response)
            return {"success": True, **parsed}
        except json.JSONDecodeError:
            return {
                "success": True,
                "overall_sentiment": "neutral",
                "confidence": 0.5,
                "impact_score": 5,
                "summary": response[:200],
            }

    async def score_resilience(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate geopolitical resilience score for a stock (1-10).

        Scoring factors:
        - Base score: 10
        - Tariff exposure: -2 for sensitive sectors
        - Geographic concentration: -2 if >30% single-country revenue
        - Supply chain risk: -1 for single-source components
        - Energy cost sensitivity: -1 for energy-intensive sectors
        """
        symbol = task.get("symbol", "")
        sector = task.get("sector", "technology")
        revenue_geo = task.get("revenue_geography", {})
        supply_chain = task.get("supply_chain", {})

        # Rule-based scoring
        score = 10.0
        factors = []

        # Tariff exposure
        tariff_sensitive = ["steel", "aluminum", "semiconductors", "automotive", "chemicals"]
        if sector.lower() in tariff_sensitive:
            score -= 2.0
            factors.append({"factor": "tariff_exposure", "impact": -2.0, "reason": f"{sector} is tariff-sensitive"})

        # Geographic concentration
        for country, pct in revenue_geo.items():
            if pct > 30 and country.lower() in ["china", "russia", "taiwan"]:
                score -= 2.0
                factors.append({
                    "factor": "geographic_concentration",
                    "impact": -2.0,
                    "reason": f"{pct}% revenue from {country}",
                })
                break

        # Supply chain risk
        if supply_chain.get("single_source"):
            score -= 1.0
            factors.append({
                "factor": "supply_chain_risk",
                "impact": -1.0,
                "reason": "Single-source critical components",
            })

        # Energy sensitivity
        energy_heavy = ["airlines", "chemicals", "steel", "mining", "manufacturing"]
        if sector.lower() in energy_heavy:
            score -= 1.0
            factors.append({
                "factor": "energy_sensitivity",
                "impact": -1.0,
                "reason": f"{sector} is energy cost sensitive",
            })

        score = max(1.0, min(10.0, score))

        # AI-enhanced analysis
        prompt = f"""Provide a brief geopolitical resilience assessment for {symbol} ({sector}).

Current score: {score}/10
Factors applied: {json.dumps(factors)}

In 2-3 sentences, explain:
1. Key geopolitical risks
2. Whether the score should be adjusted
3. Recommended actions if score drops below 5"""

        ai_analysis = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.2
        )

        # Auto-actions based on score
        auto_actions = []
        if score < 5:
            auto_actions.append("⚠️ Auto-tighten stop-loss to 3%")
            auto_actions.append("📊 Increase position monitoring frequency")
        if score < 3:
            auto_actions.append("🚨 Consider reducing position size by 50%")

        return {
            "success": True,
            "symbol": symbol,
            "resilience_score": round(score, 1),
            "max_score": 10,
            "risk_level": "low" if score >= 7 else "medium" if score >= 5 else "high",
            "factors": factors,
            "auto_actions": auto_actions,
            "ai_analysis": ai_analysis,
            "scored_at": datetime.now().isoformat(),
        }

    async def track_influencer(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Track market influencers and their potential impact."""
        influencer = task.get("influencer", "")

        influencer_profiles = {
            "elon_musk": {
                "name": "Elon Musk",
                "role": "CEO Tesla/SpaceX, Owner X",
                "sectors": ["EV", "Space", "AI", "Social Media"],
                "impact_radius": "global",
                "volatility_factor": 9,
            },
            "jerome_powell": {
                "name": "Jerome Powell",
                "role": "Fed Chair",
                "sectors": ["All — monetary policy affects everything"],
                "impact_radius": "global",
                "volatility_factor": 10,
            },
            "warren_buffett": {
                "name": "Warren Buffett",
                "role": "Berkshire Hathaway CEO",
                "sectors": ["Insurance", "Banking", "Consumer", "Energy"],
                "impact_radius": "global",
                "volatility_factor": 7,
            },
            "donald_trump": {
                "name": "Donald Trump",
                "role": "US President",
                "sectors": ["Trade", "Energy", "Defense", "Healthcare"],
                "impact_radius": "global",
                "volatility_factor": 10,
            },
        }

        profile = influencer_profiles.get(
            influencer.lower().replace(" ", "_"),
            {"name": influencer, "role": "Unknown", "sectors": [], "impact_radius": "unknown", "volatility_factor": 5},
        )

        prompt = f"""Analyze the current market influence of {profile['name']} ({profile['role']}).

What are their recent public statements/actions that could affect markets?
Which specific stocks or sectors are most impacted?
Rate current influence level: Low/Medium/High/Critical.

Be concise — 3-4 sentences max."""

        analysis = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.3
        )

        return {
            "success": True,
            "influencer": profile,
            "analysis": analysis,
            "tracked_at": datetime.now().isoformat(),
        }

    async def detect_policy_shock(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Detect sudden policy changes that could shock markets."""
        news_items = task.get("news", [])
        portfolio_symbols = task.get("portfolio", [])

        prompt = f"""Analyze these news items for potential policy shocks.

News:
{chr(10).join(f"- {n}" for n in news_items[:10])}

Portfolio stocks to check impact on: {', '.join(portfolio_symbols)}

Respond in JSON:
{{
  "shock_detected": true/false,
  "severity": "low|medium|high|critical",
  "affected_stocks": ["SYM1", "SYM2"],
  "description": "brief description",
  "recommended_actions": ["action1", "action2"]
}}"""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.1, json_mode=True
        )

        try:
            parsed = json.loads(response)
            return {"success": True, **parsed}
        except json.JSONDecodeError:
            return {
                "success": True,
                "shock_detected": False,
                "severity": "low",
                "description": "No significant policy shocks detected",
            }

    async def generate_knowledge_pill(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a daily market brief ('Knowledge Pill')."""
        region = task.get("region", "global")

        prompt = f"""Generate today's Knowledge Pill — a concise daily market brief for {region} markets.

Include exactly 5 key takeaways with emoji prefixes:
1. Major index movements (S&P 500, Nasdaq, Dow / Nifty, Sensex)
2. Fed/RBI policy updates
3. Top sector movers
4. Key earnings or economic data
5. One actionable insight

Keep each takeaway to 1-2 sentences. Be specific with numbers."""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.3
        )

        return {
            "success": True,
            "region": region,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "knowledge_pill": response,
            "generated_at": datetime.now().isoformat(),
        }
