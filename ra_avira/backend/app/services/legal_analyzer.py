"""
Legal & Fraud Detection Engine
Detects fraud, legal risks, RERA violations, and generates due diligence reports.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date


@dataclass
class FraudIndicator:
    type: str
    severity: str  # low, medium, high, critical
    description: str
    confidence: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class LegalRiskReport:
    overall_risk: str  # low, medium, high, critical
    fraud_probability: float  # 0-1
    risk_score: int  # 0-100
    indicators: List[FraudIndicator] = field(default_factory=list)
    rera_status: Optional[str] = None
    encumbrance_status: Optional[str] = None
    due_diligence_checklist: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class LegalAnalyzer:
    """Detects fraud, legal risks, and provides due diligence for Indian real estate."""

    # Price anomaly thresholds (Hyderabad-specific per sqft ranges by area)
    PRICE_RANGES = {
        "gachibowli": (7000, 15000),
        "kokapet": (8000, 18000),
        "financial_district": (9000, 16000),
        "kondapur": (6000, 12000),
        "madhapur": (7000, 14000),
        "jubilee_hills": (12000, 35000),
        "hitech_city": (8000, 15000),
        "narsingi": (6000, 12000),
        "tellapur": (5000, 10000),
    }

    # Common fraud patterns in Indian real estate
    FRAUD_PATTERNS = {
        "fake_urgency": [
            r"last\s*(?:unit|flat|plot)",
            r"only\s*\d+\s*(?:left|remaining)",
            r"booking\s*closes?\s*(?:today|tomorrow)",
            r"price\s*(?:hike|increase)\s*(?:from|after)",
        ],
        "unrealistic_returns": [
            r"guaranteed\s*(?:returns?|appreciation)",
            r"\d{2,3}\s*%\s*(?:returns?|appreciation|growth)",
            r"double\s*(?:in|within)\s*\d+\s*years?",
        ],
        "missing_rera": [
            r"rera\s*(?:applied|pending|in\s*process)",
            r"pre-?launch",
            r"(?:no|without)\s*rera",
        ],
    }

    def analyze_property_risk(
        self,
        price: int,
        area_sqft: int,
        area_name: str,
        builder_name: Optional[str] = None,
        rera_id: Optional[str] = None,
        age_years: int = 0,
        listing_text: str = "",
        builder_complaints: int = 0,
        builder_delayed_projects: int = 0,
        has_encumbrance_cert: bool = False,
        has_title_deed: bool = False,
        has_khata: bool = False,
        transaction_type: str = "sale",
    ) -> LegalRiskReport:
        """Comprehensive legal and fraud risk analysis."""
        indicators: List[FraudIndicator] = []
        
        # 1. Price anomaly detection
        price_per_sqft = price // area_sqft if area_sqft > 0 else 0
        area_slug = area_name.lower().replace(" ", "_")
        price_range = self.PRICE_RANGES.get(area_slug, (5000, 20000))
        
        if price_per_sqft < price_range[0] * 0.7:
            indicators.append(FraudIndicator(
                type="price_too_low",
                severity="high",
                description=f"Price ₹{price_per_sqft}/sqft is suspiciously below market range ₹{price_range[0]}-{price_range[1]}/sqft for {area_name}",
                confidence=0.8,
                evidence=[f"Market range: ₹{price_range[0]}-₹{price_range[1]}/sqft", f"Listed: ₹{price_per_sqft}/sqft"],
            ))
        elif price_per_sqft > price_range[1] * 1.3:
            indicators.append(FraudIndicator(
                type="overpriced",
                severity="medium",
                description=f"Price ₹{price_per_sqft}/sqft is significantly above market range for {area_name}",
                confidence=0.7,
                evidence=[f"Market range: ₹{price_range[0]}-₹{price_range[1]}/sqft", f"Listed: ₹{price_per_sqft}/sqft"],
            ))

        # 2. RERA compliance check
        if not rera_id and age_years == 0:
            indicators.append(FraudIndicator(
                type="no_rera",
                severity="critical",
                description="No RERA registration for new property. This is illegal under RERA Act 2016.",
                confidence=0.95,
                evidence=["RERA mandatory for all new projects", "Missing RERA ID in listing"],
            ))

        # 3. Builder reputation analysis
        if builder_complaints > 5:
            severity = "critical" if builder_complaints > 20 else "high" if builder_complaints > 10 else "medium"
            indicators.append(FraudIndicator(
                type="builder_complaints",
                severity=severity,
                description=f"Builder has {builder_complaints} registered complaints",
                confidence=0.85,
                evidence=[f"{builder_complaints} complaints on record"],
            ))

        if builder_delayed_projects > 2:
            indicators.append(FraudIndicator(
                type="builder_delays",
                severity="high",
                description=f"Builder has {builder_delayed_projects} delayed projects",
                confidence=0.9,
                evidence=[f"{builder_delayed_projects} projects delayed beyond RERA timeline"],
            ))

        # 4. Listing text fraud pattern detection
        for fraud_type, patterns in self.FRAUD_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, listing_text, re.IGNORECASE):
                    indicators.append(FraudIndicator(
                        type=fraud_type,
                        severity="medium" if fraud_type == "fake_urgency" else "high",
                        description=f"Detected {fraud_type.replace('_', ' ')} pattern in listing",
                        confidence=0.7,
                        evidence=[f"Pattern matched: {pattern}"],
                    ))
                    break

        # 5. Document verification
        if transaction_type == "resale":
            if not has_encumbrance_cert:
                indicators.append(FraudIndicator(
                    type="missing_ec",
                    severity="critical",
                    description="No Encumbrance Certificate. Property may have pending loans or disputes.",
                    confidence=0.9,
                    evidence=["EC is mandatory for all resale transactions"],
                ))
            if not has_title_deed:
                indicators.append(FraudIndicator(
                    type="missing_title",
                    severity="critical",
                    description="No clear title deed. Ownership cannot be verified.",
                    confidence=0.95,
                    evidence=["Title deed required to establish ownership chain"],
                ))
            if not has_khata:
                indicators.append(FraudIndicator(
                    type="missing_khata",
                    severity="high",
                    description="No Khata certificate. Property tax records unclear.",
                    confidence=0.8,
                    evidence=["Khata required for property tax and mutation"],
                ))

        # Calculate overall risk
        fraud_probability = self._calculate_fraud_probability(indicators)
        risk_score = self._calculate_risk_score(indicators)
        overall_risk = self._score_to_risk_level(risk_score)

        # Generate due diligence checklist
        checklist = self._generate_checklist(transaction_type, age_years, rera_id)

        # Generate recommendations
        recommendations = self._generate_recommendations(indicators, overall_risk)

        return LegalRiskReport(
            overall_risk=overall_risk,
            fraud_probability=fraud_probability,
            risk_score=risk_score,
            indicators=indicators,
            rera_status="registered" if rera_id else "not_registered",
            encumbrance_status="verified" if has_encumbrance_cert else "not_verified",
            due_diligence_checklist=checklist,
            recommendations=recommendations,
        )

    def _calculate_fraud_probability(self, indicators: List[FraudIndicator]) -> float:
        if not indicators:
            return 0.0
        
        max_confidence = max(i.confidence for i in indicators)
        severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.6, "critical": 0.9}
        
        weighted_sum = sum(
            severity_weights.get(i.severity, 0.5) * i.confidence
            for i in indicators
        )
        
        # Normalize to 0-1
        normalized = min(1.0, weighted_sum / max(1, len(indicators)))
        return round(normalized, 2)

    def _calculate_risk_score(self, indicators: List[FraudIndicator]) -> int:
        if not indicators:
            return 0
        
        severity_scores = {"low": 10, "medium": 25, "high": 50, "critical": 80}
        total = sum(severity_scores.get(i.severity, 25) for i in indicators)
        return min(100, total)

    def _score_to_risk_level(self, score: int) -> str:
        if score >= 70:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        return "low"

    def _generate_checklist(self, transaction_type: str, age_years: int, rera_id: Optional[str]) -> List[Dict]:
        checklist = [
            {"item": "Verify RERA registration on rera.telangana.gov.in", "critical": True, "status": "verified" if rera_id else "pending"},
            {"item": "Obtain 15-year Encumbrance Certificate (EC)", "critical": True, "status": "pending"},
            {"item": "Verify title deed chain (minimum 30 years)", "critical": True, "status": "pending"},
            {"item": "Check GHMC approved building plan", "critical": True, "status": "pending"},
            {"item": "Verify Khata/Patta in owner's name", "critical": True, "status": "pending"},
            {"item": "Check for pending property tax dues", "critical": False, "status": "pending"},
            {"item": "Verify NOC from housing society (if applicable)", "critical": False, "status": "pending"},
            {"item": "Check locality for flood zone designation", "critical": False, "status": "pending"},
            {"item": "Verify water and sewage connection", "critical": False, "status": "pending"},
            {"item": "Check for pending litigation on eCourts", "critical": True, "status": "pending"},
        ]

        if transaction_type == "resale":
            checklist.extend([
                {"item": "Verify sale deed registration at SRO", "critical": True, "status": "pending"},
                {"item": "Check for existing mortgage/lien", "critical": True, "status": "pending"},
                {"item": "Obtain NOC from existing loan bank", "critical": True, "status": "pending"},
                {"item": "Verify mutation in revenue records", "critical": True, "status": "pending"},
            ])

        if age_years == 0:
            checklist.extend([
                {"item": "Verify builder's other project delivery track record", "critical": True, "status": "pending"},
                {"item": "Check RERA quarterly update compliance", "critical": False, "status": "pending"},
                {"item": "Verify Commencement Certificate (CC)", "critical": True, "status": "pending"},
                {"item": "Check for Occupancy Certificate (OC) timeline", "critical": True, "status": "pending"},
            ])

        return checklist

    def _generate_recommendations(self, indicators: List[FraudIndicator], overall_risk: str) -> List[str]:
        recommendations = []
        
        if overall_risk == "critical":
            recommendations.append("⚠️ HIGH RISK: Do NOT proceed without thorough legal verification by a property lawyer.")
        elif overall_risk == "high":
            recommendations.append("⚠️ Significant risks detected. Engage a property lawyer before proceeding.")

        critical_types = {i.type for i in indicators if i.severity == "critical"}
        
        if "no_rera" in critical_types:
            recommendations.append("Verify RERA status at rera.telangana.gov.in before any payment.")
        if "missing_ec" in critical_types:
            recommendations.append("Obtain 15-year EC from Sub-Registrar Office immediately.")
        if "missing_title" in critical_types:
            recommendations.append("Do NOT pay advance without verifying complete title chain.")
        if "builder_complaints" in {i.type for i in indicators}:
            recommendations.append("Research builder reviews on Google, MouthShut, and consumer forums.")
        if "overpriced" in {i.type for i in indicators}:
            recommendations.append("Property appears overpriced. Negotiate or explore alternatives in the area.")
        if "price_too_low" in {i.type for i in indicators}:
            recommendations.append("Suspiciously low price. Possible fraud or undisclosed issues. Investigate thoroughly.")

        if not recommendations:
            recommendations.append("✅ No major red flags detected. Standard due diligence recommended.")

        return recommendations


legal_analyzer = LegalAnalyzer()
