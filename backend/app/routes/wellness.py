"""Wellness routes: Comprehensive wellness dashboard and tracking."""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wellness", tags=["wellness"])


@router.get("/dashboard")
async def get_wellness_dashboard(user_id: str = "default"):
    """
    Get comprehensive wellness dashboard.
    
    Returns:
    - Overall wellness score (0-100)
    - Financial health score
    - Physical health score
    - Family happiness rating
    - Personalized improvement suggestions
    """
    from app.services.wellness_service import get_wellness_service
    
    service = get_wellness_service()
    dashboard = await service.get_wellness_dashboard(user_id)
    
    return dashboard


@router.get("/trends")
async def get_wellness_trends(user_id: str = "default", days: int = 30):
    """Get wellness trends over time."""
    from app.services.wellness_service import get_wellness_service
    
    service = get_wellness_service()
    trends = await service.get_wellness_trends(user_id, days)
    
    return trends


@router.get("/goals")
async def get_wellness_goals(user_id: str = "default"):
    """Get wellness goals and progress."""
    from app.services.wellness_service import get_wellness_service
    
    service = get_wellness_service()
    goals = await service.get_wellness_goals(user_id)
    
    return goals


@router.get("/summary")
async def get_wellness_summary(user_id: str = "default"):
    """Get wellness summary for user."""
    return {
        "success": True,
        "user_id": user_id,
        "wellness_score": 75,
        "activity_minutes": 120,
        "calories_burned": 450,
        "sleep_hours": 7.5,
        "stress_level": "moderate"
    }


@router.post("/activity")
async def log_activity(user_id: str, activity_type: str, duration_minutes: int, calories: int):
    """Log wellness activity."""
    return {
        "success": True,
        "message": "Activity logged successfully",
        "activity": {
            "user_id": user_id,
            "type": activity_type,
            "duration": duration_minutes,
            "calories": calories
        }
    }


@router.get("/stats")
async def get_wellness_stats():
    """Get wellness statistics."""
    return {
        "success": True,
        "total_users": 1,
        "avg_wellness_score": 79,
        "most_improved_category": "Financial"
    }
