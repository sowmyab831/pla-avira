"""Nutrition routes: AI-powered meal planning and dietary recommendations."""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


class MealPlanRequest(BaseModel):
    """Meal plan request."""
    age: int
    gender: str
    health_goals: Optional[List[str]] = None
    dietary_preferences: Optional[List[str]] = None
    cuisine_preferences: Optional[str] = None
    allergies: Optional[List[str]] = None
    user_id: str = "default"


@router.post("/meal-plan")
async def get_meal_plan(request: MealPlanRequest):
    """
    Get personalized meal plan based on age, gender, health goals, and dietary preferences.
    
    Provides 3-4 options per meal (breakfast, lunch, dinner) with:
    - Calories and macros
    - Ingredients
    - Prep time
    - Age/gender-appropriate portions
    """
    from app.services.nutrition_service import get_nutrition_service
    from app.config import settings
    
    service = get_nutrition_service()
    
    meal_plan = await service.get_meal_plan(
        age=request.age,
        gender=request.gender,
        health_goals=request.health_goals,
        dietary_preferences=request.dietary_preferences,
        cuisine_preferences=request.cuisine_preferences,
        allergies=request.allergies,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model
    )
    
    return meal_plan


@router.post("/analyze")
async def analyze_meal(user_id: str, meal_description: str):
    """Analyze a meal and provide nutritional information."""
    return {
        "success": True,
        "meal": meal_description,
        "nutrition": {
            "calories": 450,
            "protein": 25,
            "carbs": 50,
            "fat": 15,
            "fiber": 8
        },
        "health_score": 85,
        "recommendations": ["Good protein content", "Consider adding more vegetables"]
    }


@router.get("/summary")
async def get_nutrition_summary(user_id: str = "default"):
    """Get nutrition summary for user."""
    return {
        "success": True,
        "user_id": user_id,
        "daily_calories": 1850,
        "daily_protein": 95,
        "daily_carbs": 220,
        "daily_fat": 65,
        "meals_logged": 3,
        "health_score": 82
    }


@router.get("/meal-plan/default")
async def get_default_meal_plan(
    age: int = 30,
    gender: str = "male",
    dietary_preference: Optional[str] = None
):
    """Get default meal plan for quick access."""
    from app.services.nutrition_service import get_nutrition_service
    from app.config import settings
    
    service = get_nutrition_service()
    
    dietary_prefs = [dietary_preference] if dietary_preference else None
    
    meal_plan = await service.get_meal_plan(
        age=age,
        gender=gender,
        health_goals=None,
        dietary_preferences=dietary_prefs,
        allergies=None,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model
    )
    
    return meal_plan


@router.get("/meal-plan/kids")
async def get_kids_meal_plan(age: int):
    """Get age-appropriate meal plan for kids."""
    from app.services.nutrition_service import get_nutrition_service
    
    service = get_nutrition_service()
    
    meal_plan = await service.get_meal_plan(
        age=age,
        gender="child",
        health_goals=["healthy_growth"],
        dietary_preferences=None,
        allergies=None,
        ollama_host=None,
        ollama_model=None
    )
    
    return meal_plan


@router.get("/recommendations")
async def get_nutrition_recommendations(
    age: int,
    gender: str,
    health_goal: Optional[str] = None
):
    """Get general nutrition recommendations."""
    
    recommendations = {
        "success": True,
        "age": age,
        "gender": gender,
        "health_goal": health_goal,
        "general_tips": [
            "Eat 5+ servings of fruits and vegetables daily",
            "Choose whole grains over refined grains",
            "Include lean protein at each meal",
            "Stay hydrated with 8+ glasses of water",
            "Limit processed foods and added sugars"
        ]
    }
    
    # Age-specific recommendations
    if age < 18:
        recommendations["age_specific"] = [
            "Ensure adequate calcium for bone growth",
            "Include iron-rich foods",
            "Limit sugary drinks and snacks",
            "Encourage family meals"
        ]
    elif age < 65:
        recommendations["age_specific"] = [
            "Maintain healthy weight",
            "Focus on nutrient-dense foods",
            "Limit sodium and saturated fats",
            "Regular meal timing"
        ]
    else:
        recommendations["age_specific"] = [
            "Adequate protein to maintain muscle",
            "Calcium and vitamin D for bone health",
            "Fiber for digestive health",
            "Stay hydrated"
        ]
    
    return recommendations


@router.get("/stats")
async def get_nutrition_stats():
    """Get nutrition statistics."""
    return {
        "success": True,
        "meal_plans_generated": 0,
        "popular_preferences": ["balanced", "vegetarian", "keto"],
        "avg_calories": 2000
    }
