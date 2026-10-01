"""
Property API Routes
CRUD operations, search, filtering for properties.
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from app.services.valuation_engine import valuation_engine, ValuationInput
from app.services.legal_analyzer import legal_analyzer
from app.services.recommendation_engine import recommendation_engine
from app.services.investment_intelligence import investment_intelligence

router = APIRouter(prefix="/api/properties", tags=["Properties"])


# ============================================================
# Pydantic Models
# ============================================================

class PropertySearchRequest(BaseModel):
    query: Optional[str] = None
    area: Optional[str] = None
    property_type: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    bedrooms: Optional[int] = None
    min_area_sqft: Optional[int] = None
    max_area_sqft: Optional[int] = None
    facing: Optional[str] = None
    possession_status: Optional[str] = None
    sort_by: str = "relevance"
    page: int = 1
    limit: int = 20


class ValuationRequest(BaseModel):
    base_price: int = Field(..., description="Property price in INR")
    area_sqft: int = Field(..., description="Total area in sq ft")
    property_type: str = Field(default="apartment")
    transaction_type: str = Field(default="sale")
    possession_status: str = Field(default="ready")
    bedrooms: int = Field(default=2)
    furnishing: str = Field(default="unfurnished")
    parking_count: int = Field(default=1)
    is_gated_community: bool = Field(default=True)
    age_years: int = Field(default=0)
    loan_amount: Optional[int] = None
    loan_tenure_years: int = Field(default=20)
    interest_rate: float = Field(default=8.5)


class LegalCheckRequest(BaseModel):
    price: int
    area_sqft: int
    area_name: str
    builder_name: Optional[str] = None
    rera_id: Optional[str] = None
    age_years: int = 0
    listing_text: str = ""
    builder_complaints: int = 0
    builder_delayed_projects: int = 0
    has_encumbrance_cert: bool = False
    has_title_deed: bool = False
    has_khata: bool = False
    transaction_type: str = "sale"


class PropertyResponse(BaseModel):
    id: str
    title: str
    property_type: str
    price: int
    price_per_sqft: Optional[int]
    bedrooms: Optional[int]
    area_sqft: Optional[int]
    area_name: Optional[str]
    address: Optional[str]
    builder_name: Optional[str]
    images: List[str] = []
    overall_score: float = 0
    fraud_probability: float = 0


# ============================================================
# Routes
# ============================================================

@router.post("/search")
async def search_properties(request: PropertySearchRequest):
    """Search properties with filters and AI-powered relevance."""
    # In production, this queries PostgreSQL + OpenSearch
    # For now, return mock data structure
    return {
        "results": [],
        "total": 0,
        "page": request.page,
        "limit": request.limit,
        "filters_applied": request.model_dump(exclude_none=True),
    }


@router.get("/feed")
async def get_property_feed(
    user_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Get personalized property feed (TikTok-style)."""
    # In production, uses recommendation engine with user signals
    return {
        "feed": [],
        "page": page,
        "has_more": False,
        "personalized": user_id is not None,
    }


@router.get("/{property_id}")
async def get_property_detail(property_id: str):
    """Get detailed property information."""
    return {
        "id": property_id,
        "message": "Property detail endpoint",
        "sections": [
            "overview", "cost_breakdown", "legal_status",
            "location_analysis", "investment_metrics", "similar_properties",
        ],
    }


@router.post("/valuation")
async def calculate_valuation(request: ValuationRequest):
    """Calculate total ownership cost breakdown."""
    inp = ValuationInput(
        base_price=request.base_price,
        area_sqft=request.area_sqft,
        property_type=request.property_type,
        transaction_type=request.transaction_type,
        possession_status=request.possession_status,
        bedrooms=request.bedrooms,
        furnishing=request.furnishing,
        parking_count=request.parking_count,
        is_gated_community=request.is_gated_community,
        age_years=request.age_years,
        loan_amount=request.loan_amount,
        loan_tenure_years=request.loan_tenure_years,
        interest_rate=request.interest_rate,
    )
    
    result = valuation_engine.calculate_total_cost(inp)
    
    return {
        "cost_breakdown": {
            "base_price": result.base_price,
            "price_per_sqft": result.price_per_sqft,
            "stamp_duty": result.stamp_duty,
            "registration_charges": result.registration_charges,
            "gst": result.gst,
            "parking_charges": result.parking_charges,
            "clubhouse_charges": result.clubhouse_charges,
            "corpus_fund": result.corpus_fund,
            "maintenance_deposit": result.maintenance_deposit,
            "legal_verification": result.legal_verification,
            "brokerage": result.brokerage,
            "interior_estimate": result.interior_estimate,
            "furnishing_estimate": result.furnishing_estimate,
            "loan_processing_fee": result.loan_processing_fee,
        },
        "totals": {
            "total_ownership_cost": result.total_ownership_cost,
            "hidden_costs_total": result.hidden_costs_total,
            "percentage_above_listed": result.percentage_above_listed,
        },
        "monthly": {
            "emi": result.monthly_emi,
            "maintenance": result.monthly_maintenance,
            "total_monthly_outgo": result.total_monthly_outgo,
        },
        "investment": {
            "estimated_rental_income": result.estimated_rental_income,
            "rental_yield_pct": result.rental_yield_pct,
            "break_even_years": result.break_even_years,
        },
        "breakdown_percentages": result.cost_breakdown_pct,
    }


@router.post("/legal-check")
async def check_legal_risk(request: LegalCheckRequest):
    """Analyze legal risks and fraud probability for a property."""
    report = legal_analyzer.analyze_property_risk(
        price=request.price,
        area_sqft=request.area_sqft,
        area_name=request.area_name,
        builder_name=request.builder_name,
        rera_id=request.rera_id,
        age_years=request.age_years,
        listing_text=request.listing_text,
        builder_complaints=request.builder_complaints,
        builder_delayed_projects=request.builder_delayed_projects,
        has_encumbrance_cert=request.has_encumbrance_cert,
        has_title_deed=request.has_title_deed,
        has_khata=request.has_khata,
        transaction_type=request.transaction_type,
    )
    
    return {
        "overall_risk": report.overall_risk,
        "fraud_probability": report.fraud_probability,
        "risk_score": report.risk_score,
        "indicators": [
            {
                "type": i.type,
                "severity": i.severity,
                "description": i.description,
                "confidence": i.confidence,
                "evidence": i.evidence,
            }
            for i in report.indicators
        ],
        "rera_status": report.rera_status,
        "encumbrance_status": report.encumbrance_status,
        "due_diligence_checklist": report.due_diligence_checklist,
        "recommendations": report.recommendations,
    }


@router.get("/compare/{property_ids}")
async def compare_properties(property_ids: str):
    """Compare multiple properties side by side."""
    ids = property_ids.split(",")
    return {
        "properties": ids,
        "comparison": [],
        "winner": None,
    }


@router.post("/{property_id}/save")
async def save_property(property_id: str, user_id: str = "demo"):
    """Save a property to user's shortlist."""
    return {"saved": True, "property_id": property_id}


@router.post("/{property_id}/schedule-visit")
async def schedule_visit(property_id: str, date: str, time: str, user_id: str = "demo"):
    """Schedule a site visit."""
    return {
        "scheduled": True,
        "property_id": property_id,
        "date": date,
        "time": time,
        "status": "pending_confirmation",
    }
