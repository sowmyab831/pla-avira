"""
Investment Intelligence Routes
Area analysis, forecasts, comparisons, and investment recommendations.
"""
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.investment_intelligence import investment_intelligence

router = APIRouter(prefix="/api/investment", tags=["Investment Intelligence"])


class InvestmentRecommendationRequest(BaseModel):
    budget: int  # in INR
    goal: str = "appreciation"  # appreciation, rental, balanced
    risk_tolerance: str = "medium"  # low, medium, high
    timeline_years: int = 5


@router.get("/areas")
async def get_all_areas():
    """Get investment profiles for all Hyderabad areas."""
    areas = investment_intelligence.get_all_areas()
    return {
        "areas": [
            {
                "name": a.name,
                "slug": a.slug,
                "current_avg_sqft": a.current_avg_sqft,
                "appreciation_1y": a.appreciation_1y,
                "appreciation_3y": a.appreciation_3y,
                "appreciation_5y": a.appreciation_5y,
                "rental_yield": a.rental_yield,
                "metro_impact": a.metro_impact,
                "infra_score": a.infra_score,
                "investment_grade": a.investment_grade,
                "forecast_5y": a.forecast_5y_appreciation,
                "risk_level": a.risk_level,
            }
            for a in areas
        ],
        "count": len(areas),
    }


@router.get("/areas/{area_slug}")
async def get_area_detail(area_slug: str):
    """Get detailed investment profile for a specific area."""
    area = investment_intelligence.get_area_profile(area_slug)
    if not area:
        return {"error": f"Area '{area_slug}' not found"}
    
    return {
        "name": area.name,
        "slug": area.slug,
        "current_avg_sqft": area.current_avg_sqft,
        "appreciation": {
            "1_year": area.appreciation_1y,
            "3_year": area.appreciation_3y,
            "5_year": area.appreciation_5y,
        },
        "rental_yield": area.rental_yield,
        "metro_impact": area.metro_impact,
        "infrastructure_score": area.infra_score,
        "demand_index": area.demand_index,
        "supply_pressure": area.supply_pressure,
        "investment_grade": area.investment_grade,
        "forecast_5y_appreciation": area.forecast_5y_appreciation,
        "risk_level": area.risk_level,
    }


@router.post("/recommend")
async def get_investment_recommendations(request: InvestmentRecommendationRequest):
    """Get AI-powered investment recommendations."""
    result = investment_intelligence.recommend_investment(
        budget=request.budget,
        goal=request.goal,
        risk_tolerance=request.risk_tolerance,
        timeline_years=request.timeline_years,
    )
    return result


@router.get("/compare")
async def compare_areas(areas: str = Query(..., description="Comma-separated area slugs")):
    """Compare multiple areas for investment."""
    area_slugs = [a.strip() for a in areas.split(",")]
    return investment_intelligence.compare_areas(area_slugs)


@router.get("/metro-impact")
async def get_metro_impact():
    """Get metro impact analysis on property prices."""
    return investment_intelligence.metro_impact_analysis()


@router.get("/hot-areas")
async def get_hot_areas():
    """Get currently trending/hot areas for investment."""
    areas = investment_intelligence.get_all_areas()
    hot = [a for a in areas if a.appreciation_1y > 12]
    
    return {
        "hot_areas": [
            {
                "name": a.name,
                "slug": a.slug,
                "appreciation_1y": a.appreciation_1y,
                "investment_grade": a.investment_grade,
                "reason": f"+{a.appreciation_1y}% in last year" + (" | Metro coming" if a.metro_impact else ""),
            }
            for a in sorted(hot, key=lambda x: x.appreciation_1y, reverse=True)
        ],
    }
