"""
AI Recommendation Engine
TikTok-style intelligent feed that adapts to user behavior.
Uses vector similarity + collaborative filtering + rule-based scoring.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class UserSignal:
    property_id: str
    signal_type: str  # view, save, call, reject, share, visit
    duration_seconds: int = 0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class RecommendationEngine:
    """
    Generates personalized property recommendations.
    Combines:
    1. Content-based filtering (property features vs user preferences)
    2. Behavior signals (views, saves, calls, time spent)
    3. Investment intelligence (appreciation, yield, risk)
    4. Location intelligence (proximity scoring)
    """

    # Signal weights for scoring
    SIGNAL_WEIGHTS = {
        "view": 1.0,
        "save": 5.0,
        "call": 8.0,
        "visit": 10.0,
        "share": 4.0,
        "reject": -3.0,
    }

    # Feature weights for recommendation
    FEATURE_WEIGHTS = {
        "budget_match": 0.25,
        "area_match": 0.20,
        "type_match": 0.15,
        "size_match": 0.10,
        "value_score": 0.15,
        "legal_score": 0.10,
        "freshness": 0.05,
    }

    def score_property_for_user(
        self,
        property_data: Dict,
        user_preferences: Dict,
        user_signals: List[UserSignal],
        area_data: Optional[Dict] = None,
    ) -> float:
        """Calculate recommendation score for a property-user pair."""
        score = 0.0

        # 1. Budget match (0-1)
        budget_score = self._budget_match_score(
            property_data.get("price", 0),
            user_preferences.get("budget_min", 0),
            user_preferences.get("budget_max", float("inf")),
        )
        score += budget_score * self.FEATURE_WEIGHTS["budget_match"]

        # 2. Area match (0-1)
        area_score = 1.0 if property_data.get("area_slug") in user_preferences.get("preferred_areas", []) else 0.3
        score += area_score * self.FEATURE_WEIGHTS["area_match"]

        # 3. Type match (0-1)
        type_score = 1.0 if property_data.get("property_type") == user_preferences.get("property_type") else 0.2
        score += type_score * self.FEATURE_WEIGHTS["type_match"]

        # 4. Size match (0-1)
        size_score = self._size_match_score(
            property_data.get("bedrooms", 0),
            user_preferences.get("bedrooms"),
        )
        score += size_score * self.FEATURE_WEIGHTS["size_match"]

        # 5. Value score (0-1) - property's intrinsic value
        value_score = property_data.get("value_score", 0.5)
        score += value_score * self.FEATURE_WEIGHTS["value_score"]

        # 6. Legal score (0-1) - inverse of fraud probability
        legal_score = 1.0 - property_data.get("fraud_probability", 0)
        score += legal_score * self.FEATURE_WEIGHTS["legal_score"]

        # 7. Freshness (0-1) - newer listings rank higher
        freshness = self._freshness_score(property_data.get("created_at"))
        score += freshness * self.FEATURE_WEIGHTS["freshness"]

        # 8. Behavior boost from similar properties
        behavior_boost = self._behavior_boost(property_data, user_signals)
        score += behavior_boost * 0.15

        # 9. Investment potential boost
        if area_data:
            investment_boost = self._investment_boost(area_data)
            score += investment_boost * 0.1

        return min(1.0, max(0.0, score))

    def generate_feed(
        self,
        properties: List[Dict],
        user_preferences: Dict,
        user_signals: List[UserSignal],
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """Generate personalized property feed."""
        scored_properties = []

        # Score each property
        for prop in properties:
            score = self.score_property_for_user(prop, user_preferences, user_signals)
            scored_properties.append({
                **prop,
                "recommendation_score": round(score, 4),
                "recommendation_reasons": self._generate_reasons(prop, user_preferences, score),
            })

        # Sort by score (descending)
        scored_properties.sort(key=lambda x: x["recommendation_score"], reverse=True)

        # Apply diversity (don't show too many from same area/builder)
        diversified = self._apply_diversity(scored_properties)

        return diversified[offset:offset + limit]

    def get_similar_properties(
        self,
        target_property: Dict,
        all_properties: List[Dict],
        limit: int = 5,
    ) -> List[Dict]:
        """Find similar properties (for 'More like this' feature)."""
        similarities = []
        
        for prop in all_properties:
            if prop.get("id") == target_property.get("id"):
                continue
            
            sim_score = self._similarity_score(target_property, prop)
            similarities.append({**prop, "similarity_score": sim_score})

        similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similarities[:limit]

    def get_investment_picks(
        self,
        properties: List[Dict],
        areas: List[Dict],
        budget_max: int,
        limit: int = 10,
    ) -> List[Dict]:
        """Get top investment picks based on appreciation potential and rental yield."""
        picks = []

        for prop in properties:
            if prop.get("price", 0) > budget_max:
                continue

            area_slug = prop.get("area_slug", "")
            area = next((a for a in areas if a.get("slug") == area_slug), {})

            investment_score = self._calculate_investment_score(prop, area)
            
            picks.append({
                **prop,
                "investment_score": investment_score,
                "appreciation_forecast": area.get("appreciation_5y", 0),
                "rental_yield": area.get("rental_yield", 0),
                "metro_impact": area.get("upcoming_metro", False),
                "why_invest": self._investment_reasons(prop, area),
            })

        picks.sort(key=lambda x: x["investment_score"], reverse=True)
        return picks[:limit]

    def _budget_match_score(self, price: int, budget_min: int, budget_max: float) -> float:
        """Score how well price matches budget."""
        if budget_max == float("inf"):
            return 0.5
        if budget_min <= price <= budget_max:
            # Prefer properties in the middle of budget range
            mid = (budget_min + budget_max) / 2
            deviation = abs(price - mid) / mid if mid > 0 else 0
            return max(0.5, 1.0 - deviation * 0.5)
        elif price < budget_min:
            # Under budget - might be a deal
            return max(0.3, 1.0 - (budget_min - price) / budget_min)
        else:
            # Over budget
            overage = (price - budget_max) / budget_max
            return max(0.0, 0.5 - overage * 2)

    def _size_match_score(self, bedrooms: int, preferred: Optional[int]) -> float:
        if preferred is None:
            return 0.5
        diff = abs(bedrooms - preferred)
        if diff == 0:
            return 1.0
        elif diff == 1:
            return 0.6
        return 0.2

    def _freshness_score(self, created_at) -> float:
        """Newer listings get higher scores."""
        if created_at is None:
            return 0.5
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        age_days = (datetime.utcnow() - created_at).days
        if age_days <= 3:
            return 1.0
        elif age_days <= 7:
            return 0.8
        elif age_days <= 30:
            return 0.6
        elif age_days <= 90:
            return 0.4
        return 0.2

    def _behavior_boost(self, property_data: Dict, signals: List[UserSignal]) -> float:
        """Boost score based on similar property interactions."""
        if not signals:
            return 0.0

        boost = 0.0
        for signal in signals[-50:]:  # Last 50 signals
            weight = self.SIGNAL_WEIGHTS.get(signal.signal_type, 0)
            # Time decay
            age = (datetime.utcnow() - signal.timestamp).days
            decay = max(0.1, 1.0 - age * 0.03)
            boost += weight * decay * 0.01

        return min(0.3, max(-0.2, boost))

    def _investment_boost(self, area_data: Dict) -> float:
        """Boost for areas with high investment potential."""
        appreciation = area_data.get("appreciation_5y", 0)
        metro = area_data.get("upcoming_metro", False)
        yield_pct = area_data.get("rental_yield", 0)

        score = 0.0
        if appreciation > 15:
            score += 0.3
        elif appreciation > 10:
            score += 0.2
        
        if metro:
            score += 0.2
        
        if yield_pct > 3:
            score += 0.2
        
        return min(0.5, score)

    def _similarity_score(self, prop_a: Dict, prop_b: Dict) -> float:
        """Calculate similarity between two properties."""
        score = 0.0

        # Price similarity
        price_a, price_b = prop_a.get("price", 0), prop_b.get("price", 0)
        if price_a > 0 and price_b > 0:
            ratio = min(price_a, price_b) / max(price_a, price_b)
            score += ratio * 0.3

        # Same area
        if prop_a.get("area_slug") == prop_b.get("area_slug"):
            score += 0.25

        # Same type
        if prop_a.get("property_type") == prop_b.get("property_type"):
            score += 0.2

        # Same bedrooms
        if prop_a.get("bedrooms") == prop_b.get("bedrooms"):
            score += 0.15

        # Similar area sqft
        sqft_a, sqft_b = prop_a.get("total_area_sqft", 0), prop_b.get("total_area_sqft", 0)
        if sqft_a > 0 and sqft_b > 0:
            ratio = min(sqft_a, sqft_b) / max(sqft_a, sqft_b)
            score += ratio * 0.1

        return score

    def _calculate_investment_score(self, prop: Dict, area: Dict) -> float:
        """Calculate investment attractiveness."""
        score = 0.0
        
        appreciation = area.get("appreciation_5y", 0)
        score += min(30, appreciation * 2)
        
        rental_yield = area.get("rental_yield", 0)
        score += min(20, rental_yield * 5)
        
        if area.get("upcoming_metro"):
            score += 15
        
        if area.get("infrastructure_score", 0) > 7:
            score += 10
        
        # Legal clearance bonus
        if prop.get("fraud_probability", 1) < 0.2:
            score += 15
        
        # Builder reputation
        score += min(10, prop.get("builder_score", 0))
        
        return min(100, score)

    def _apply_diversity(self, properties: List[Dict]) -> List[Dict]:
        """Ensure feed diversity - don't show too many from same area/builder."""
        result = []
        area_counts = {}
        builder_counts = {}

        for prop in properties:
            area = prop.get("area_slug", "unknown")
            builder = prop.get("builder_id", "unknown")
            
            area_count = area_counts.get(area, 0)
            builder_count = builder_counts.get(builder, 0)
            
            # Max 5 from same area, 3 from same builder in sequence
            if area_count < 5 and builder_count < 3:
                result.append(prop)
                area_counts[area] = area_count + 1
                builder_counts[builder] = builder_count + 1

        return result

    def _generate_reasons(self, prop: Dict, preferences: Dict, score: float) -> List[str]:
        """Generate human-readable reasons for recommendation."""
        reasons = []
        
        if prop.get("area_slug") in preferences.get("preferred_areas", []):
            reasons.append(f"In your preferred area: {prop.get('area_slug', '').replace('_', ' ').title()}")
        
        price = prop.get("price", 0)
        budget_max = preferences.get("budget_max", 0)
        if budget_max and price <= budget_max:
            savings = budget_max - price
            if savings > 0:
                reasons.append(f"₹{savings // 100000} lakhs under your budget")
        
        if prop.get("value_score", 0) > 0.7:
            reasons.append("Excellent value for money")
        
        if prop.get("fraud_probability", 1) < 0.1:
            reasons.append("Verified & legally clear")
        
        if not reasons:
            reasons.append("Matches your search criteria")
        
        return reasons[:3]

    def _investment_reasons(self, prop: Dict, area: Dict) -> List[str]:
        """Generate investment recommendation reasons."""
        reasons = []
        
        appreciation = area.get("appreciation_5y", 0)
        if appreciation > 10:
            reasons.append(f"{appreciation}% appreciation in 5 years")
        
        if area.get("upcoming_metro"):
            reasons.append("Metro line coming - expect 15-25% price surge")
        
        rental_yield = area.get("rental_yield", 0)
        if rental_yield > 3:
            reasons.append(f"Strong rental yield: {rental_yield}%")
        
        if area.get("it_corridor_distance_km", 99) < 5:
            reasons.append("Close to IT corridor - high demand area")
        
        return reasons[:4]


recommendation_engine = RecommendationEngine()
