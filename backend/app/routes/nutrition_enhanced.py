"""
Enhanced Nutrition Routes with Meal Logging and Calorie Tracking
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, date
import logging
import httpx

from app.config import settings
from app.services.llm_client import generate as llm_generate

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])
logger = logging.getLogger(__name__)

# In-memory storage (replace with database in production)
meal_logs: List[Dict] = []
user_profiles: Dict[str, Dict] = {}


class FoodItem(BaseModel):
    name: str
    servings: float
    calories_per_serving: Optional[float] = None


class MealLog(BaseModel):
    user_id: str = "default"
    meal_type: str  # breakfast, lunch, dinner, snack
    foods: List[FoodItem]
    meal_time: Optional[str] = None


class UserProfile(BaseModel):
    user_id: str = "default"
    height_cm: float
    weight_kg: float
    age: int
    gender: str  # male, female, other
    activity_level: str = "moderate"  # sedentary, light, moderate, active, very_active
    health_goals: Optional[List[str]] = None  # weight_loss, muscle_gain, maintenance, health


# Comprehensive nutrition database (subset shown)
NUTRITION_DB = {
    "oatmeal": {"calories": 150, "protein": 5, "carbs": 27, "fat": 3, "fiber": 4, "vitamins": ["B1", "Iron", "Magnesium"]},
    "banana": {"calories": 105, "protein": 1.3, "carbs": 27, "fat": 0.4, "fiber": 3, "vitamins": ["C", "B6", "Potassium"]},
    "almonds": {"calories": 164, "protein": 6, "carbs": 6, "fat": 14, "fiber": 3.5, "vitamins": ["E", "Magnesium", "Calcium"]},
    "chicken breast": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0, "vitamins": ["B6", "B12", "Niacin"]},
    "rice": {"calories": 206, "protein": 4.3, "carbs": 45, "fat": 0.4, "fiber": 0.6, "vitamins": ["B1", "B3", "Iron"]},
    "broccoli": {"calories": 55, "protein": 3.7, "carbs": 11, "fat": 0.6, "fiber": 5, "vitamins": ["C", "K", "Folate"]},
    "salmon": {"calories": 206, "protein": 22, "carbs": 0, "fat": 13, "fiber": 0, "vitamins": ["D", "B12", "Omega-3"]},
    "eggs": {"calories": 78, "protein": 6.3, "carbs": 0.6, "fat": 5.3, "fiber": 0, "vitamins": ["A", "D", "B12", "Choline"]},
    "milk": {"calories": 149, "protein": 7.7, "carbs": 11.7, "fat": 7.9, "fiber": 0, "vitamins": ["D", "Calcium", "B12"]},
    "bread": {"calories": 79, "protein": 2.7, "carbs": 15, "fat": 1, "fiber": 0.8, "vitamins": ["B1", "Iron", "Folate"]},
    "apple": {"calories": 95, "protein": 0.5, "carbs": 25, "fat": 0.3, "fiber": 4, "vitamins": ["C", "Potassium"]},
    "yogurt": {"calories": 100, "protein": 10, "carbs": 13, "fat": 0.4, "fiber": 0, "vitamins": ["Calcium", "B12", "Probiotics"]},
    "pasta": {"calories": 221, "protein": 8, "carbs": 43, "fat": 1.3, "fiber": 2.5, "vitamins": ["B1", "B3", "Iron"]},
    "spinach": {"calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "fiber": 2.2, "vitamins": ["A", "C", "K", "Iron"]},
    "avocado": {"calories": 160, "protein": 2, "carbs": 8.5, "fat": 15, "fiber": 7, "vitamins": ["K", "Folate", "C", "E"]},
}


@router.post("/log-meal")
async def log_meal(meal: MealLog):
    """
    Log a meal and get instant nutritional analysis.
    Calculates calories, macros, vitamins, and provides health recommendations.
    """
    total_nutrition = {
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
        "fiber": 0,
        "vitamins": set()
    }
    
    food_details = []
    
    for food in meal.foods:
        food_name = food.name.lower()
        
        # Look up nutrition data
        nutrition = NUTRITION_DB.get(food_name)
        
        if not nutrition:
            # Try to find partial match
            for key in NUTRITION_DB.keys():
                if food_name in key or key in food_name:
                    nutrition = NUTRITION_DB[key]
                    break
        
        if nutrition:
            # Calculate for servings
            food_details.append({
                "name": food.name,
                "servings": food.servings,
                "calories": nutrition["calories"] * food.servings,
                "protein": nutrition["protein"] * food.servings,
                "carbs": nutrition["carbs"] * food.servings,
                "fat": nutrition["fat"] * food.servings,
                "fiber": nutrition["fiber"] * food.servings,
                "vitamins": nutrition["vitamins"]
            })
            
            total_nutrition["calories"] += nutrition["calories"] * food.servings
            total_nutrition["protein"] += nutrition["protein"] * food.servings
            total_nutrition["carbs"] += nutrition["carbs"] * food.servings
            total_nutrition["fat"] += nutrition["fat"] * food.servings
            total_nutrition["fiber"] += nutrition["fiber"] * food.servings
            total_nutrition["vitamins"].update(nutrition["vitamins"])
    
    # Store meal log
    meal_entry = {
        "user_id": meal.user_id,
        "meal_type": meal.meal_type,
        "foods": food_details,
        "total_nutrition": {
            "calories": round(total_nutrition["calories"], 1),
            "protein": round(total_nutrition["protein"], 1),
            "carbs": round(total_nutrition["carbs"], 1),
            "fat": round(total_nutrition["fat"], 1),
            "fiber": round(total_nutrition["fiber"], 1),
            "vitamins": list(total_nutrition["vitamins"])
        },
        "meal_time": meal.meal_time or datetime.now().isoformat(),
        "logged_at": datetime.now().isoformat()
    }
    
    meal_logs.append(meal_entry)
    
    # Generate health recommendations
    recommendations = _generate_meal_recommendations(meal_entry["total_nutrition"], meal.meal_type)
    
    return {
        "success": True,
        "meal_logged": meal_entry,
        "health_score": _calculate_health_score(meal_entry["total_nutrition"], meal.meal_type),
        "recommendations": recommendations
    }


@router.post("/analyze-day")
async def analyze_daily_nutrition(user_id: str, target_date: Optional[str] = None):
    """
    Analyze total nutrition for a day and provide personalized recommendations
    based on user profile (height, weight, age, gender, activity level).
    """
    if not target_date:
        target_date = date.today().isoformat()
    
    # Get user's meals for the day
    daily_meals = [m for m in meal_logs if m["user_id"] == user_id and m["logged_at"].startswith(target_date)]
    
    # Calculate daily totals
    daily_totals = {
        "calories": sum(m["total_nutrition"]["calories"] for m in daily_meals),
        "protein": sum(m["total_nutrition"]["protein"] for m in daily_meals),
        "carbs": sum(m["total_nutrition"]["carbs"] for m in daily_meals),
        "fat": sum(m["total_nutrition"]["fat"] for m in daily_meals),
        "fiber": sum(m["total_nutrition"]["fiber"] for m in daily_meals),
        "vitamins": set()
    }
    
    for meal in daily_meals:
        daily_totals["vitamins"].update(meal["total_nutrition"]["vitamins"])
    
    # Get user profile for personalized recommendations
    profile = user_profiles.get(user_id, {
        "height_cm": 175,
        "weight_kg": 75,
        "age": 30,
        "gender": "male",
        "activity_level": "moderate"
    })
    
    # Calculate recommended daily intake
    recommended = _calculate_recommended_intake(profile)
    
    # Generate AI-powered recommendations
    ai_recommendations = await _get_ai_nutrition_recommendations(
        daily_totals, recommended, profile
    )
    
    return {
        "success": True,
        "date": target_date,
        "meals_logged": len(daily_meals),
        "daily_totals": {
            "calories": round(daily_totals["calories"], 1),
            "protein": round(daily_totals["protein"], 1),
            "carbs": round(daily_totals["carbs"], 1),
            "fat": round(daily_totals["fat"], 1),
            "fiber": round(daily_totals["fiber"], 1),
            "vitamins": list(daily_totals["vitamins"])
        },
        "recommended_intake": recommended,
        "progress": {
            "calories": f"{daily_totals['calories'] / recommended['calories'] * 100:.1f}%",
            "protein": f"{daily_totals['protein'] / recommended['protein'] * 100:.1f}%",
            "carbs": f"{daily_totals['carbs'] / recommended['carbs'] * 100:.1f}%",
            "fat": f"{daily_totals['fat'] / recommended['fat'] * 100:.1f}%"
        },
        "health_score": _calculate_daily_health_score(daily_totals, recommended),
        "recommendations": ai_recommendations,
        "user_profile": profile
    }


@router.post("/profile")
async def update_user_profile(profile: UserProfile):
    """Update user's nutrition profile for personalized recommendations."""
    user_profiles[profile.user_id] = profile.dict()
    
    return {
        "success": True,
        "message": "Profile updated successfully",
        "profile": profile
    }


@router.get("/meals/today")
async def get_todays_meals(user_id: str = "default"):
    """Get all meals logged today."""
    today = date.today().isoformat()
    todays_meals = [m for m in meal_logs if m["user_id"] == user_id and m["logged_at"].startswith(today)]
    
    return {
        "success": True,
        "date": today,
        "meals": todays_meals,
        "count": len(todays_meals)
    }


def _calculate_recommended_intake(profile: Dict) -> Dict[str, float]:
    """Calculate recommended daily intake based on user profile."""
    # Basal Metabolic Rate (BMR) using Mifflin-St Jeor Equation
    weight = profile.get("weight_kg", 75)
    height = profile.get("height_cm", 175)
    age = profile.get("age", 30)
    gender = profile.get("gender", "male")
    
    if gender.lower() == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    
    # Activity multiplier
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    
    multiplier = activity_multipliers.get(profile.get("activity_level", "moderate"), 1.55)
    tdee = bmr * multiplier  # Total Daily Energy Expenditure
    
    return {
        "calories": round(tdee, 0),
        "protein": round(weight * 1.6, 1),  # 1.6g per kg body weight
        "carbs": round(tdee * 0.5 / 4, 1),  # 50% of calories from carbs
        "fat": round(tdee * 0.3 / 9, 1),  # 30% of calories from fat
        "fiber": 25 if gender.lower() == "female" else 38,
        "water_liters": round(weight * 0.033, 1)
    }


def _calculate_health_score(nutrition: Dict, meal_type: str) -> int:
    """Calculate health score for a meal (0-100)."""
    score = 50  # Base score
    
    # Protein bonus
    if nutrition["protein"] > 20:
        score += 15
    elif nutrition["protein"] > 10:
        score += 10
    
    # Fiber bonus
    if nutrition["fiber"] > 5:
        score += 15
    elif nutrition["fiber"] > 3:
        score += 10
    
    # Vitamin diversity bonus
    if len(nutrition.get("vitamins", [])) >= 5:
        score += 10
    elif len(nutrition.get("vitamins", [])) >= 3:
        score += 5
    
    # Balanced macros bonus
    total_cals = nutrition["calories"]
    if total_cals > 0:
        protein_pct = (nutrition["protein"] * 4) / total_cals
        carbs_pct = (nutrition["carbs"] * 4) / total_cals
        fat_pct = (nutrition["fat"] * 9) / total_cals
        
        if 0.15 <= protein_pct <= 0.35 and 0.45 <= carbs_pct <= 0.65 and 0.20 <= fat_pct <= 0.35:
            score += 10
    
    return min(score, 100)


def _calculate_daily_health_score(daily_totals: Dict, recommended: Dict) -> int:
    """Calculate overall health score for the day."""
    score = 50
    
    # Calorie target (within 10% of recommended)
    cal_ratio = daily_totals["calories"] / recommended["calories"]
    if 0.9 <= cal_ratio <= 1.1:
        score += 20
    elif 0.8 <= cal_ratio <= 1.2:
        score += 10
    
    # Protein target
    protein_ratio = daily_totals["protein"] / recommended["protein"]
    if protein_ratio >= 0.9:
        score += 15
    elif protein_ratio >= 0.7:
        score += 10
    
    # Fiber target
    fiber_ratio = daily_totals["fiber"] / recommended["fiber"]
    if fiber_ratio >= 0.8:
        score += 15
    elif fiber_ratio >= 0.6:
        score += 10
    
    return min(score, 100)


def _generate_meal_recommendations(nutrition: Dict, meal_type: str) -> List[str]:
    """Generate recommendations for a meal."""
    recs = []
    
    if nutrition["protein"] < 15:
        recs.append("💪 Add more protein (eggs, chicken, fish, beans)")
    
    if nutrition["fiber"] < 3:
        recs.append("🥦 Include more fiber (vegetables, whole grains, fruits)")
    
    if len(nutrition.get("vitamins", [])) < 3:
        recs.append("🍎 Add variety for more vitamins and minerals")
    
    if nutrition["calories"] > 800 and meal_type != "dinner":
        recs.append("⚖️ Consider smaller portions to balance daily intake")
    
    if not recs:
        recs.append("✅ Well-balanced meal! Great choices.")
    
    return recs


async def _get_ai_nutrition_recommendations(
    daily_totals: Dict,
    recommended: Dict,
    profile: Dict
) -> List[str]:
    """Get AI-powered nutrition recommendations using Ollama."""
    prompt = f"""Analyze this person's daily nutrition and provide 3-5 specific recommendations.

PROFILE:
- Age: {profile.get('age')} years
- Gender: {profile.get('gender')}
- Weight: {profile.get('weight_kg')} kg
- Height: {profile.get('height_cm')} cm
- Activity: {profile.get('activity_level')}

TODAY'S INTAKE:
- Calories: {daily_totals['calories']:.0f} / {recommended['calories']:.0f} ({daily_totals['calories']/recommended['calories']*100:.0f}%)
- Protein: {daily_totals['protein']:.1f}g / {recommended['protein']:.1f}g
- Carbs: {daily_totals['carbs']:.1f}g / {recommended['carbs']:.1f}g
- Fat: {daily_totals['fat']:.1f}g / {recommended['fat']:.1f}g
- Fiber: {daily_totals['fiber']:.1f}g / {recommended['fiber']:.0f}g

Provide specific, actionable recommendations to improve their nutrition."""

    try:
        ai_text = await llm_generate(
            prompt, task="fast", temperature=0.7, max_tokens=300, timeout=60,
        )

        if ai_text:
            # Parse AI response into list
            recommendations = [line.strip() for line in ai_text.split('\n') if line.strip() and len(line.strip()) > 10]
            return recommendations[:5]
    except Exception as e:
        logger.error(f"AI nutrition recommendation error: {e}")
    
    # Fallback recommendations
    recs = []
    
    cal_ratio = daily_totals["calories"] / recommended["calories"]
    if cal_ratio < 0.8:
        recs.append(f"📊 You're {(1-cal_ratio)*100:.0f}% below your calorie target. Add nutrient-dense snacks.")
    elif cal_ratio > 1.2:
        recs.append(f"⚠️ You're {(cal_ratio-1)*100:.0f}% over your calorie target. Consider smaller portions.")
    
    if daily_totals["protein"] / recommended["protein"] < 0.8:
        recs.append("💪 Increase protein intake with lean meats, fish, eggs, or legumes.")
    
    if daily_totals["fiber"] / recommended["fiber"] < 0.6:
        recs.append("🥗 Add more fiber with vegetables, fruits, and whole grains.")
    
    if len(daily_totals.get("vitamins", [])) < 8:
        recs.append("🌈 Eat a variety of colorful fruits and vegetables for more vitamins.")
    
    if not recs:
        recs.append("✅ Great job! Your nutrition is well-balanced today.")
    
    return recs


@router.get("/food-database")
async def search_food_database(query: str):
    """Search nutrition database for food items."""
    query_lower = query.lower()
    results = []
    
    for food_name, nutrition in NUTRITION_DB.items():
        if query_lower in food_name or food_name in query_lower:
            results.append({
                "name": food_name,
                "nutrition": nutrition
            })
    
    return {
        "success": True,
        "query": query,
        "results": results,
        "count": len(results)
    }
