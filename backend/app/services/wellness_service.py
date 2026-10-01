"""
Wellness Service - Comprehensive Wellness Dashboard
Calculates and tracks overall wellness across financial, health, and family dimensions
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WellnessService:
    """
    Comprehensive wellness tracking service with:
    - Financial health score
    - Physical health score
    - Family happiness rating
    - Overall wellness score
    - Personalized improvement suggestions
    """
    
    async def get_wellness_dashboard(
        self,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get complete wellness dashboard for user."""
        
        # Get individual scores
        financial_score = await self._calculate_financial_health(user_id)
        health_score = await self._calculate_physical_health(user_id)
        family_score = await self._calculate_family_happiness(user_id)
        
        # Calculate overall wellness score (weighted average)
        overall_score = int(
            (financial_score["score"] * 0.35) +
            (health_score["score"] * 0.35) +
            (family_score["score"] * 0.30)
        )
        
        # Determine overall rating
        if overall_score >= 80:
            overall_rating = "Excellent"
            overall_color = "green"
        elif overall_score >= 60:
            overall_rating = "Good"
            overall_color = "green"
        elif overall_score >= 40:
            overall_rating = "Fair"
            overall_color = "yellow"
        else:
            overall_rating = "Needs Attention"
            overall_color = "red"
        
        # Get improvement suggestions
        suggestions = self._get_improvement_suggestions(
            financial_score, health_score, family_score
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "overall": {
                "score": overall_score,
                "rating": overall_rating,
                "color": overall_color,
                "message": self._get_overall_message(overall_score)
            },
            "financial": financial_score,
            "health": health_score,
            "family": family_score,
            "suggestions": suggestions,
            "last_updated": datetime.now().isoformat()
        }
    
    async def _calculate_financial_health(self, user_id: str) -> Dict[str, Any]:
        """Calculate financial health score."""
        
        # In production, this would analyze:
        # - Income vs expenses
        # - Savings rate
        # - Debt-to-income ratio
        # - Investment portfolio performance
        # - Emergency fund status
        
        # Mock calculation for demo
        score = 75
        
        return {
            "score": score,
            "rating": "Good" if score >= 70 else "Fair" if score >= 50 else "Needs Improvement",
            "color": "green" if score >= 70 else "yellow" if score >= 50 else "red",
            "metrics": {
                "savings_rate": 15,  # percentage
                "debt_to_income": 25,  # percentage
                "emergency_fund_months": 4,
                "investment_growth": 8.5  # percentage
            },
            "strengths": [
                "Good savings rate (15%)",
                "Manageable debt levels",
                "Diversified investments"
            ],
            "areas_to_improve": [
                "Build emergency fund to 6 months",
                "Reduce discretionary spending"
            ]
        }
    
    async def _calculate_physical_health(self, user_id: str) -> Dict[str, Any]:
        """Calculate physical health score."""
        
        # In production, this would analyze:
        # - Recent health reports
        # - Vital signs trends
        # - Exercise frequency
        # - Sleep quality
        # - Nutrition adherence
        
        # Mock calculation for demo
        score = 80
        
        return {
            "score": score,
            "rating": "Good" if score >= 70 else "Fair" if score >= 50 else "Needs Attention",
            "color": "green" if score >= 70 else "yellow" if score >= 50 else "red",
            "metrics": {
                "exercise_days_per_week": 4,
                "avg_sleep_hours": 7.5,
                "nutrition_score": 75,
                "stress_level": "moderate"
            },
            "strengths": [
                "Regular exercise routine",
                "Adequate sleep",
                "Balanced nutrition"
            ],
            "areas_to_improve": [
                "Increase exercise to 5 days/week",
                "Stress management techniques",
                "Annual health checkup due"
            ]
        }
    
    async def _calculate_family_happiness(self, user_id: str) -> Dict[str, Any]:
        """Calculate family happiness rating."""
        
        # In production, this would analyze:
        # - Family member check-ins
        # - Shared activities
        # - Communication patterns
        # - Support needs
        # - Family events participation
        
        # Mock calculation for demo
        score = 85
        
        return {
            "score": score,
            "rating": "Excellent" if score >= 80 else "Good" if score >= 60 else "Fair",
            "color": "green" if score >= 70 else "yellow" if score >= 50 else "red",
            "metrics": {
                "family_activities_per_month": 8,
                "quality_time_hours_per_week": 12,
                "communication_score": 85,
                "support_level": "high"
            },
            "strengths": [
                "Regular family activities",
                "Strong communication",
                "High support level"
            ],
            "areas_to_improve": [
                "Schedule more one-on-one time",
                "Plan family vacation"
            ]
        }
    
    def _get_improvement_suggestions(
        self,
        financial: Dict[str, Any],
        health: Dict[str, Any],
        family: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get personalized improvement suggestions."""
        
        suggestions = []
        
        # Financial suggestions
        if financial["score"] < 70:
            suggestions.append({
                "category": "Financial",
                "priority": "high" if financial["score"] < 50 else "medium",
                "title": "Improve Financial Health",
                "description": "Focus on building emergency fund and reducing debt",
                "action_items": financial.get("areas_to_improve", [])
            })
        
        # Health suggestions
        if health["score"] < 70:
            suggestions.append({
                "category": "Health",
                "priority": "high" if health["score"] < 50 else "medium",
                "title": "Enhance Physical Wellness",
                "description": "Increase exercise frequency and improve sleep quality",
                "action_items": health.get("areas_to_improve", [])
            })
        
        # Family suggestions
        if family["score"] < 70:
            suggestions.append({
                "category": "Family",
                "priority": "medium",
                "title": "Strengthen Family Bonds",
                "description": "Schedule more quality time and family activities",
                "action_items": family.get("areas_to_improve", [])
            })
        
        # If all scores are good, provide maintenance suggestions
        if not suggestions:
            suggestions.append({
                "category": "Overall",
                "priority": "low",
                "title": "Maintain Current Wellness",
                "description": "Keep up the great work! Continue your healthy habits.",
                "action_items": [
                    "Continue regular exercise routine",
                    "Maintain savings rate",
                    "Keep family connections strong"
                ]
            })
        
        return suggestions
    
    def _get_overall_message(self, score: int) -> str:
        """Get personalized message based on overall score."""
        
        if score >= 80:
            return "Excellent! You're doing great across all areas of wellness. Keep up the fantastic work!"
        elif score >= 60:
            return "Good job! You're on the right track. Focus on the suggested improvements to reach excellent wellness."
        elif score >= 40:
            return "You're making progress, but there's room for improvement. Focus on the priority areas to boost your wellness."
        else:
            return "Let's work together to improve your wellness. Start with the high-priority suggestions and take it one step at a time."
    
    async def get_wellness_trends(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get wellness trends over time."""
        
        # In production, this would query historical data
        # Mock trend data for demo
        
        return {
            "success": True,
            "period_days": days,
            "trends": {
                "financial": {
                    "direction": "improving",
                    "change": +5,
                    "data_points": [70, 72, 73, 75]
                },
                "health": {
                    "direction": "stable",
                    "change": 0,
                    "data_points": [80, 79, 81, 80]
                },
                "family": {
                    "direction": "improving",
                    "change": +3,
                    "data_points": [82, 83, 84, 85]
                },
                "overall": {
                    "direction": "improving",
                    "change": +3,
                    "data_points": [75, 76, 78, 79]
                }
            }
        }
    
    async def get_wellness_goals(self, user_id: str) -> Dict[str, Any]:
        """Get wellness goals and progress."""
        
        return {
            "success": True,
            "goals": [
                {
                    "id": "goal_1",
                    "category": "Financial",
                    "title": "Build 6-month emergency fund",
                    "target": 6,
                    "current": 4,
                    "unit": "months",
                    "progress": 67,
                    "deadline": "2026-06-30"
                },
                {
                    "id": "goal_2",
                    "category": "Health",
                    "title": "Exercise 5 days per week",
                    "target": 5,
                    "current": 4,
                    "unit": "days/week",
                    "progress": 80,
                    "deadline": "2026-03-31"
                },
                {
                    "id": "goal_3",
                    "category": "Family",
                    "title": "Plan family vacation",
                    "target": 1,
                    "current": 0,
                    "unit": "vacation",
                    "progress": 25,
                    "deadline": "2026-07-15"
                }
            ]
        }


# Singleton instance
_wellness_service: Optional[WellnessService] = None


def get_wellness_service() -> WellnessService:
    """Get wellness service instance."""
    global _wellness_service
    if _wellness_service is None:
        _wellness_service = WellnessService()
    return _wellness_service
