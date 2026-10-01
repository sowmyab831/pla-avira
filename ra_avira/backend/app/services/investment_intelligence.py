"""
Investment Intelligence Engine
Provides area appreciation forecasts, ROI projections, and investment recommendations
for Hyderabad real estate.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AreaInvestmentProfile:
    name: str
    slug: str
    current_avg_sqft: int
    appreciation_1y: float
    appreciation_3y: float
    appreciation_5y: float
    rental_yield: float
    metro_impact: bool
    infra_score: float
    demand_index: float  # 0-10
    supply_pressure: float  # 0-10 (higher = more supply = price pressure)
    investment_grade: str  # A+, A, B+, B, C
    forecast_5y_appreciation: float
    risk_level: str  # low, medium, high


# Hyderabad investment data (curated market intelligence)
HYDERABAD_AREAS: Dict[str, AreaInvestmentProfile] = {
    "kokapet": AreaInvestmentProfile(
        name="Kokapet",
        slug="kokapet",
        current_avg_sqft=11000,
        appreciation_1y=18.5,
        appreciation_3y=52.0,
        appreciation_5y=95.0,
        rental_yield=2.8,
        metro_impact=True,
        infra_score=8.5,
        demand_index=9.0,
        supply_pressure=6.0,
        investment_grade="A+",
        forecast_5y_appreciation=60.0,
        risk_level="medium",
    ),
    "financial_district": AreaInvestmentProfile(
        name="Financial District",
        slug="financial_district",
        current_avg_sqft=12000,
        appreciation_1y=15.0,
        appreciation_3y=45.0,
        appreciation_5y=85.0,
        rental_yield=3.2,
        metro_impact=True,
        infra_score=9.0,
        demand_index=8.5,
        supply_pressure=4.5,
        investment_grade="A+",
        forecast_5y_appreciation=50.0,
        risk_level="low",
    ),
    "gachibowli": AreaInvestmentProfile(
        name="Gachibowli",
        slug="gachibowli",
        current_avg_sqft=9500,
        appreciation_1y=12.0,
        appreciation_3y=38.0,
        appreciation_5y=70.0,
        rental_yield=3.5,
        metro_impact=True,
        infra_score=8.0,
        demand_index=8.0,
        supply_pressure=5.0,
        investment_grade="A",
        forecast_5y_appreciation=45.0,
        risk_level="low",
    ),
    "kondapur": AreaInvestmentProfile(
        name="Kondapur",
        slug="kondapur",
        current_avg_sqft=8000,
        appreciation_1y=10.0,
        appreciation_3y=32.0,
        appreciation_5y=60.0,
        rental_yield=3.8,
        metro_impact=True,
        infra_score=7.5,
        demand_index=7.5,
        supply_pressure=5.5,
        investment_grade="A",
        forecast_5y_appreciation=40.0,
        risk_level="low",
    ),
    "madhapur": AreaInvestmentProfile(
        name="Madhapur",
        slug="madhapur",
        current_avg_sqft=9000,
        appreciation_1y=8.0,
        appreciation_3y=28.0,
        appreciation_5y=55.0,
        rental_yield=4.0,
        metro_impact=True,
        infra_score=7.0,
        demand_index=7.0,
        supply_pressure=4.0,
        investment_grade="A",
        forecast_5y_appreciation=35.0,
        risk_level="low",
    ),
    "hitech_city": AreaInvestmentProfile(
        name="Hitech City",
        slug="hitech_city",
        current_avg_sqft=10000,
        appreciation_1y=9.0,
        appreciation_3y=30.0,
        appreciation_5y=58.0,
        rental_yield=4.2,
        metro_impact=True,
        infra_score=8.0,
        demand_index=7.5,
        supply_pressure=3.5,
        investment_grade="A",
        forecast_5y_appreciation=35.0,
        risk_level="low",
    ),
    "tellapur": AreaInvestmentProfile(
        name="Tellapur",
        slug="tellapur",
        current_avg_sqft=7000,
        appreciation_1y=22.0,
        appreciation_3y=60.0,
        appreciation_5y=110.0,
        rental_yield=2.5,
        metro_impact=True,
        infra_score=7.0,
        demand_index=8.5,
        supply_pressure=7.5,
        investment_grade="A+",
        forecast_5y_appreciation=70.0,
        risk_level="medium",
    ),
    "narsingi": AreaInvestmentProfile(
        name="Narsingi",
        slug="narsingi",
        current_avg_sqft=8500,
        appreciation_1y=14.0,
        appreciation_3y=42.0,
        appreciation_5y=75.0,
        rental_yield=2.9,
        metro_impact=False,
        infra_score=7.0,
        demand_index=7.0,
        supply_pressure=6.0,
        investment_grade="B+",
        forecast_5y_appreciation=45.0,
        risk_level="medium",
    ),
    "jubilee_hills": AreaInvestmentProfile(
        name="Jubilee Hills",
        slug="jubilee_hills",
        current_avg_sqft=18000,
        appreciation_1y=6.0,
        appreciation_3y=22.0,
        appreciation_5y=40.0,
        rental_yield=2.2,
        metro_impact=False,
        infra_score=9.0,
        demand_index=6.0,
        supply_pressure=2.0,
        investment_grade="B+",
        forecast_5y_appreciation=25.0,
        risk_level="low",
    ),
}


class InvestmentIntelligence:
    """Investment analysis and forecasting for Hyderabad real estate."""

    def get_area_profile(self, area_slug: str) -> Optional[AreaInvestmentProfile]:
        """Get investment profile for an area."""
        return HYDERABAD_AREAS.get(area_slug)

    def get_all_areas(self) -> List[AreaInvestmentProfile]:
        """Get all area profiles sorted by investment grade."""
        grade_order = {"A+": 0, "A": 1, "B+": 2, "B": 3, "C": 4}
        areas = list(HYDERABAD_AREAS.values())
        areas.sort(key=lambda x: grade_order.get(x.investment_grade, 5))
        return areas

    def recommend_investment(
        self,
        budget: int,
        goal: str = "appreciation",  # appreciation, rental, balanced
        risk_tolerance: str = "medium",  # low, medium, high
        timeline_years: int = 5,
    ) -> Dict:
        """Recommend best investment areas based on budget and goals."""
        recommendations = []

        for slug, area in HYDERABAD_AREAS.items():
            # Check if budget can buy a decent property in this area
            min_property_cost = area.current_avg_sqft * 1000  # ~1000 sqft minimum
            if min_property_cost > budget:
                continue

            # Risk filter
            if risk_tolerance == "low" and area.risk_level != "low":
                continue
            if risk_tolerance == "medium" and area.risk_level == "high":
                continue

            # Score based on goal
            score = self._score_area_for_goal(area, goal, timeline_years)
            
            # Estimated property size affordable
            affordable_sqft = budget // area.current_avg_sqft
            
            # 5-year value projection
            future_value = int(budget * (1 + area.forecast_5y_appreciation / 100))
            
            # Annual rental income estimate
            monthly_rental = int(affordable_sqft * area.rental_yield * area.current_avg_sqft / 1200)
            annual_rental = monthly_rental * 12

            recommendations.append({
                "area": area.name,
                "slug": slug,
                "investment_grade": area.investment_grade,
                "score": round(score, 1),
                "current_price_sqft": area.current_avg_sqft,
                "affordable_sqft": affordable_sqft,
                "forecast_5y_appreciation": area.forecast_5y_appreciation,
                "estimated_5y_value": future_value,
                "estimated_profit_5y": future_value - budget,
                "annual_rental_estimate": annual_rental,
                "rental_yield": area.rental_yield,
                "risk_level": area.risk_level,
                "metro_impact": area.metro_impact,
                "why": self._generate_investment_thesis(area, goal),
                "risks": self._identify_risks(area),
            })

        # Sort by score
        recommendations.sort(key=lambda x: x["score"], reverse=True)

        return {
            "budget": budget,
            "goal": goal,
            "risk_tolerance": risk_tolerance,
            "timeline_years": timeline_years,
            "recommendations": recommendations[:5],
            "market_summary": self._market_summary(),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def compare_areas(self, area_slugs: List[str]) -> Dict:
        """Compare multiple areas side by side."""
        comparison = []
        for slug in area_slugs:
            area = HYDERABAD_AREAS.get(slug)
            if area:
                comparison.append({
                    "name": area.name,
                    "slug": slug,
                    "price_sqft": area.current_avg_sqft,
                    "appreciation_1y": area.appreciation_1y,
                    "appreciation_5y": area.appreciation_5y,
                    "rental_yield": area.rental_yield,
                    "metro_impact": area.metro_impact,
                    "infra_score": area.infra_score,
                    "investment_grade": area.investment_grade,
                    "forecast_5y": area.forecast_5y_appreciation,
                    "risk": area.risk_level,
                })

        # Determine winner for each metric
        if comparison:
            metrics = ["appreciation_1y", "appreciation_5y", "rental_yield", "forecast_5y"]
            winners = {}
            for metric in metrics:
                best = max(comparison, key=lambda x: x.get(metric, 0))
                winners[metric] = best["name"]
            
            return {"areas": comparison, "winners": winners}
        
        return {"areas": [], "winners": {}}

    def metro_impact_analysis(self) -> Dict:
        """Analyze impact of upcoming metro on property prices."""
        metro_areas = [a for a in HYDERABAD_AREAS.values() if a.metro_impact]
        
        return {
            "metro_corridors": [
                {
                    "name": "Corridor 1: Miyapur - LB Nagar (Operational)",
                    "status": "operational",
                    "impact": "15-25% appreciation since launch",
                },
                {
                    "name": "Corridor 2: JBS - Falaknuma (Operational)",
                    "status": "operational",
                    "impact": "10-20% appreciation",
                },
                {
                    "name": "Corridor 3: Nagole - Raidurg (Operational)",
                    "status": "operational",
                    "impact": "20-30% appreciation near stations",
                },
                {
                    "name": "Extension: Raidurg - Kokapet - Financial District",
                    "status": "under_construction",
                    "expected_completion": "2026",
                    "expected_impact": "25-40% appreciation expected",
                },
                {
                    "name": "Extension: BHEL - Lakdikapul",
                    "status": "planned",
                    "expected_impact": "15-25% when operational",
                },
            ],
            "benefiting_areas": [
                {
                    "area": a.name,
                    "current_price": a.current_avg_sqft,
                    "expected_boost": f"{int(a.forecast_5y_appreciation * 0.3)}% additional from metro",
                }
                for a in metro_areas
            ],
            "recommendation": "Properties within 1km of upcoming metro stations historically see 25-40% premium after operations begin.",
        }

    def _score_area_for_goal(self, area: AreaInvestmentProfile, goal: str, years: int) -> float:
        """Score an area based on investment goal."""
        if goal == "appreciation":
            return (
                area.forecast_5y_appreciation * 0.4 +
                area.demand_index * 5 +
                (10 if area.metro_impact else 0) +
                area.infra_score * 2 -
                area.supply_pressure * 2
            )
        elif goal == "rental":
            return (
                area.rental_yield * 15 +
                area.demand_index * 3 +
                area.infra_score * 2 -
                area.supply_pressure * 1
            )
        else:  # balanced
            return (
                area.forecast_5y_appreciation * 0.25 +
                area.rental_yield * 10 +
                area.demand_index * 4 +
                area.infra_score * 2 +
                (8 if area.metro_impact else 0) -
                area.supply_pressure * 1.5
            )

    def _generate_investment_thesis(self, area: AreaInvestmentProfile, goal: str) -> List[str]:
        """Generate human-readable investment thesis."""
        reasons = []
        
        if area.appreciation_5y > 80:
            reasons.append(f"Strong historical growth: {area.appreciation_5y}% in 5 years")
        if area.metro_impact:
            reasons.append("Metro connectivity boosting demand")
        if area.infra_score > 8:
            reasons.append("Excellent infrastructure development")
        if area.demand_index > 8:
            reasons.append("Very high demand from IT professionals")
        if area.rental_yield > 3.5:
            reasons.append(f"Strong rental yield: {area.rental_yield}%")
        if area.forecast_5y_appreciation > 50:
            reasons.append(f"Expected {area.forecast_5y_appreciation}% appreciation in 5 years")
        
        return reasons[:4]

    def _identify_risks(self, area: AreaInvestmentProfile) -> List[str]:
        """Identify investment risks for an area."""
        risks = []
        
        if area.supply_pressure > 7:
            risks.append("High supply may slow price growth")
        if area.risk_level == "medium":
            risks.append("Moderate price volatility expected")
        if area.rental_yield < 2.5:
            risks.append("Low rental yield - appreciation play only")
        if area.appreciation_1y > 20:
            risks.append("Recent rapid appreciation - possible correction risk")
        
        if not risks:
            risks.append("Low risk - established area with stable demand")
        
        return risks

    def _market_summary(self) -> Dict:
        """Generate overall Hyderabad market summary."""
        areas = list(HYDERABAD_AREAS.values())
        avg_appreciation = sum(a.appreciation_1y for a in areas) / len(areas)
        
        return {
            "city": "Hyderabad",
            "market_sentiment": "Bullish",
            "avg_appreciation_1y": round(avg_appreciation, 1),
            "top_performing": "Tellapur (+22% YoY)",
            "highest_rental": "Hitech City (4.2% yield)",
            "most_affordable_growth": "Tellapur (₹7,000/sqft, 22% growth)",
            "drivers": [
                "IT/Tech sector expansion",
                "Metro phase 2 construction",
                "Amazon, Google, Apple campus expansions",
                "NRI investment inflows",
                "Infrastructure development (ORR, SRDP)",
            ],
            "risks": [
                "Oversupply in some corridors",
                "Interest rate uncertainty",
                "Global IT slowdown risk",
            ],
        }


investment_intelligence = InvestmentIntelligence()
