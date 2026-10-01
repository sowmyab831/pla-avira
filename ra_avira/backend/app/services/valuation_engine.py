"""
Property Valuation Engine
Calculates true ownership cost, market value, and investment metrics for Hyderabad properties.
"""
import math
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from app.config import settings


@dataclass
class ValuationInput:
    base_price: int  # in INR
    area_sqft: int
    property_type: str  # apartment, villa, plot
    transaction_type: str  # sale, resale
    possession_status: str  # ready, under_construction
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    parking_count: int = 1
    is_gated_community: bool = True
    bedrooms: int = 2
    furnishing: str = "unfurnished"
    age_years: int = 0
    loan_amount: Optional[int] = None
    loan_tenure_years: int = 20
    interest_rate: float = 8.5


@dataclass
class CostBreakdownResult:
    base_price: int
    price_per_sqft: int
    
    # Government charges
    stamp_duty: int
    registration_charges: int
    gst: int
    
    # Builder charges
    parking_charges: int
    clubhouse_charges: int
    corpus_fund: int
    maintenance_deposit: int
    legal_verification: int
    
    # Hidden costs
    brokerage: int
    interior_estimate: int
    furnishing_estimate: int
    loan_processing_fee: int
    
    # Totals
    total_ownership_cost: int
    hidden_costs_total: int
    percentage_above_listed: float
    
    # Monthly
    monthly_emi: int
    monthly_maintenance: int
    total_monthly_outgo: int
    
    # Investment metrics
    estimated_rental_income: int
    rental_yield_pct: float
    break_even_years: float
    
    # Breakdown percentages
    cost_breakdown_pct: Dict[str, float] = field(default_factory=dict)


class ValuationEngine:
    """Hyderabad-specific property valuation engine."""

    # Telangana stamp duty and registration rates
    STAMP_DUTY_PCT = 5.0
    REGISTRATION_PCT = 0.5
    GST_UNDER_CONSTRUCTION = 5.0  # without ITC
    GST_AFFORDABLE = 1.0  # properties under 45 lakh

    # Typical builder charges in Hyderabad
    PARKING_COVERED = 500000  # per slot
    PARKING_OPEN = 200000
    CLUBHOUSE_PER_SQFT = 50
    CORPUS_FUND_MONTHS = 24  # months of maintenance
    MAINTENANCE_DEPOSIT_MONTHS = 12
    MAINTENANCE_PER_SQFT = 4  # monthly

    # Interior costs per sqft by type
    INTERIOR_BASIC_PER_SQFT = 800
    INTERIOR_PREMIUM_PER_SQFT = 1500
    INTERIOR_LUXURY_PER_SQFT = 2500

    # Furnishing estimates
    FURNISHING_SEMI = {2: 500000, 3: 700000, 4: 1000000}
    FURNISHING_FULL = {2: 1000000, 3: 1500000, 4: 2200000}

    # Rental yields by area (monthly per sqft)
    RENTAL_YIELDS = {
        "gachibowli": 18,
        "kondapur": 20,
        "madhapur": 22,
        "hitech_city": 24,
        "kokapet": 15,
        "financial_district": 16,
        "jubilee_hills": 14,
        "narsingi": 14,
        "tellapur": 12,
        "default": 16,
    }

    def calculate_total_cost(self, inp: ValuationInput) -> CostBreakdownResult:
        """Calculate complete ownership cost breakdown."""
        base_price = inp.base_price
        price_per_sqft = base_price // inp.area_sqft if inp.area_sqft > 0 else 0

        # Government charges
        stamp_duty = int(base_price * self.STAMP_DUTY_PCT / 100)
        registration = int(base_price * self.REGISTRATION_PCT / 100)

        # GST (only for under-construction)
        gst = 0
        if inp.possession_status == "under_construction":
            if base_price <= 4500000:
                gst = int(base_price * self.GST_AFFORDABLE / 100)
            else:
                gst = int(base_price * self.GST_UNDER_CONSTRUCTION / 100)

        # Builder charges
        parking = inp.parking_count * self.PARKING_COVERED if inp.is_gated_community else 0
        clubhouse = int(inp.area_sqft * self.CLUBHOUSE_PER_SQFT) if inp.is_gated_community else 0
        monthly_maintenance = int(inp.area_sqft * self.MAINTENANCE_PER_SQFT)
        corpus_fund = monthly_maintenance * self.CORPUS_FUND_MONTHS
        maintenance_deposit = monthly_maintenance * self.MAINTENANCE_DEPOSIT_MONTHS

        # Legal
        legal_verification = 25000 if inp.transaction_type == "resale" else 15000

        # Brokerage (typically 2% for resale, 0 for new)
        brokerage = int(base_price * 0.02) if inp.transaction_type == "resale" else 0

        # Interior estimate
        interior_per_sqft = self.INTERIOR_BASIC_PER_SQFT
        if price_per_sqft > 8000:
            interior_per_sqft = self.INTERIOR_PREMIUM_PER_SQFT
        if price_per_sqft > 12000:
            interior_per_sqft = self.INTERIOR_LUXURY_PER_SQFT
        interior_estimate = int(inp.area_sqft * interior_per_sqft)

        # Furnishing
        furnishing_estimate = 0
        if inp.furnishing == "semi":
            furnishing_estimate = self.FURNISHING_SEMI.get(inp.bedrooms, 600000)
        elif inp.furnishing == "fully":
            furnishing_estimate = self.FURNISHING_FULL.get(inp.bedrooms, 1200000)

        # Loan processing
        loan_amount = inp.loan_amount or int(base_price * 0.8)
        loan_processing_fee = int(loan_amount * 0.005)  # 0.5% typical

        # Total
        total_ownership_cost = (
            base_price + stamp_duty + registration + gst +
            parking + clubhouse + corpus_fund + maintenance_deposit +
            legal_verification + brokerage + interior_estimate +
            furnishing_estimate + loan_processing_fee
        )

        hidden_costs_total = total_ownership_cost - base_price
        pct_above = (hidden_costs_total / base_price * 100) if base_price > 0 else 0

        # EMI calculation
        monthly_emi = self._calculate_emi(loan_amount, inp.interest_rate, inp.loan_tenure_years)
        total_monthly = monthly_emi + monthly_maintenance

        # Rental yield
        rental_per_sqft = self.RENTAL_YIELDS.get("default", 16)
        rental_income = int(inp.area_sqft * rental_per_sqft)
        rental_yield = (rental_income * 12 / total_ownership_cost * 100) if total_ownership_cost > 0 else 0
        break_even = total_ownership_cost / (rental_income * 12) if rental_income > 0 else 999

        # Cost breakdown percentages
        breakdown_pct = {
            "base_price": base_price / total_ownership_cost * 100,
            "stamp_duty": stamp_duty / total_ownership_cost * 100,
            "registration": registration / total_ownership_cost * 100,
            "gst": gst / total_ownership_cost * 100,
            "parking": parking / total_ownership_cost * 100,
            "brokerage": brokerage / total_ownership_cost * 100,
            "interior": interior_estimate / total_ownership_cost * 100,
            "others": (clubhouse + corpus_fund + maintenance_deposit + legal_verification + furnishing_estimate + loan_processing_fee) / total_ownership_cost * 100,
        }

        return CostBreakdownResult(
            base_price=base_price,
            price_per_sqft=price_per_sqft,
            stamp_duty=stamp_duty,
            registration_charges=registration,
            gst=gst,
            parking_charges=parking,
            clubhouse_charges=clubhouse,
            corpus_fund=corpus_fund,
            maintenance_deposit=maintenance_deposit,
            legal_verification=legal_verification,
            brokerage=brokerage,
            interior_estimate=interior_estimate,
            furnishing_estimate=furnishing_estimate,
            loan_processing_fee=loan_processing_fee,
            total_ownership_cost=total_ownership_cost,
            hidden_costs_total=hidden_costs_total,
            percentage_above_listed=round(pct_above, 1),
            monthly_emi=monthly_emi,
            monthly_maintenance=monthly_maintenance,
            total_monthly_outgo=total_monthly,
            estimated_rental_income=rental_income,
            rental_yield_pct=round(rental_yield, 2),
            break_even_years=round(break_even, 1),
            cost_breakdown_pct=breakdown_pct,
        )

    def estimate_market_value(
        self,
        area_avg_price_sqft: int,
        carpet_area: int,
        floor_number: int,
        total_floors: int,
        age_years: int,
        facing: str,
        amenities_count: int,
        builder_reputation: float,
    ) -> Dict:
        """Estimate fair market value based on area trends and property attributes."""
        base_value = area_avg_price_sqft * carpet_area

        # Floor premium (higher floors command 2-5% premium)
        floor_factor = 1.0
        if total_floors > 0:
            floor_pct = floor_number / total_floors
            if floor_pct > 0.7:
                floor_factor = 1.05
            elif floor_pct > 0.4:
                floor_factor = 1.02

        # Age depreciation (1-2% per year for first 10 years, then 0.5%)
        age_factor = 1.0
        if age_years <= 10:
            age_factor = max(0.8, 1 - (age_years * 0.015))
        else:
            age_factor = max(0.6, 0.85 - ((age_years - 10) * 0.005))

        # Facing premium
        facing_factors = {
            "East": 1.05, "North": 1.03, "NE": 1.04,
            "West": 0.98, "South": 0.97, "SW": 0.96,
            "SE": 1.01, "NW": 1.02,
        }
        facing_factor = facing_factors.get(facing, 1.0)

        # Amenities factor
        amenity_factor = min(1.10, 1 + (amenities_count * 0.005))

        # Builder reputation
        builder_factor = 0.9 + (builder_reputation * 0.02)  # 0-10 scale

        estimated_value = int(
            base_value * floor_factor * age_factor * facing_factor * amenity_factor * builder_factor
        )

        return {
            "estimated_market_value": estimated_value,
            "price_per_sqft_estimated": estimated_value // carpet_area if carpet_area > 0 else 0,
            "factors": {
                "floor_premium": round((floor_factor - 1) * 100, 1),
                "age_depreciation": round((1 - age_factor) * 100, 1),
                "facing_impact": round((facing_factor - 1) * 100, 1),
                "amenities_premium": round((amenity_factor - 1) * 100, 1),
                "builder_premium": round((builder_factor - 1) * 100, 1),
            },
            "confidence": 0.75,  # Base confidence, improved with more data
        }

    def investment_score(
        self,
        price: int,
        area_appreciation_5y: float,
        rental_yield: float,
        metro_proximity: bool,
        upcoming_infra: bool,
        builder_reputation: float,
        legal_clear: bool,
    ) -> Dict:
        """Calculate investment attractiveness score (0-100)."""
        score = 0

        # Appreciation potential (0-30)
        if area_appreciation_5y > 15:
            score += 30
        elif area_appreciation_5y > 10:
            score += 25
        elif area_appreciation_5y > 5:
            score += 15
        else:
            score += 5

        # Rental yield (0-20)
        if rental_yield > 4:
            score += 20
        elif rental_yield > 3:
            score += 15
        elif rental_yield > 2:
            score += 10
        else:
            score += 5

        # Infrastructure (0-20)
        if metro_proximity:
            score += 10
        if upcoming_infra:
            score += 10

        # Builder (0-15)
        score += min(15, int(builder_reputation * 1.5))

        # Legal (0-15)
        if legal_clear:
            score += 15

        return {
            "investment_score": min(100, score),
            "rating": self._score_to_rating(score),
            "recommendation": self._score_to_recommendation(score),
        }

    def _calculate_emi(self, principal: int, annual_rate: float, years: int) -> int:
        """Calculate monthly EMI."""
        if principal <= 0 or years <= 0:
            return 0
        monthly_rate = annual_rate / 12 / 100
        n = years * 12
        emi = principal * monthly_rate * math.pow(1 + monthly_rate, n) / (math.pow(1 + monthly_rate, n) - 1)
        return int(emi)

    def _score_to_rating(self, score: int) -> str:
        if score >= 80:
            return "EXCELLENT"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "AVERAGE"
        else:
            return "BELOW_AVERAGE"

    def _score_to_recommendation(self, score: int) -> str:
        if score >= 80:
            return "Strong Buy - Excellent investment potential"
        elif score >= 60:
            return "Buy - Good value with solid fundamentals"
        elif score >= 40:
            return "Hold - Average returns expected"
        else:
            return "Avoid - Better options available in this budget"


valuation_engine = ValuationEngine()
