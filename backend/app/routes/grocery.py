"""Grocery tracking and meal planning routes."""
import logging
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.models.grocery import MealPlan, Recipe, GroceryItem, ShoppingList, NutritionalGoals
from app.services.meal_planner import get_meal_planner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/grocery", tags=["grocery"])


class MealPlanRequest(BaseModel):
    """Meal plan generation request."""
    user_id: str = "default"
    start_date: date
    days: int = 7
    preferences: Optional[dict] = None


@router.post("/meal-plan/generate")
async def generate_meal_plan(request: MealPlanRequest):
    """Generate meal plan based on health goals and preferences."""
    planner = get_meal_planner()
    
    meal_plans = await planner.generate_meal_plan(
        request.user_id,
        request.start_date,
        request.days,
        preferences=request.preferences
    )
    
    return {
        "success": True,
        "start_date": request.start_date,
        "days": request.days,
        "meal_plans": meal_plans
    }


@router.post("/recipes/suggest")
async def suggest_recipes(
    available_ingredients: List[str],
    meal_type: Optional[str] = None
):
    """Suggest recipes based on available ingredients."""
    planner = get_meal_planner()
    
    recipes = await planner.suggest_recipes(
        available_ingredients,
        meal_type=meal_type
    )
    
    return {
        "success": True,
        "ingredients_provided": len(available_ingredients),
        "recipes_found": len(recipes),
        "recipes": recipes
    }


@router.post("/shopping-list/generate")
async def generate_shopping_list(
    meal_plans: List[dict],
    current_inventory: List[dict] = []
):
    """Generate shopping list from meal plans."""
    planner = get_meal_planner()
    
    # Convert dicts to models
    from app.models.grocery import MealPlan, GroceryItem
    
    meal_plan_objects = [MealPlan(**mp) for mp in meal_plans]
    inventory_objects = [GroceryItem(**item) for item in current_inventory]
    
    shopping_list = await planner.generate_shopping_list(
        meal_plan_objects,
        inventory_objects
    )
    
    return {
        "success": True,
        "shopping_list": shopping_list
    }


@router.get("/recipes")
async def list_recipes():
    """List all available recipes."""
    planner = get_meal_planner()
    recipes = planner.get_all_recipes()
    return {"success": True, "count": len(recipes), "recipes": recipes}


@router.get("/recipes/{recipe_id}")
async def get_recipe(recipe_id: str):
    """Get a single recipe by ID."""
    planner = get_meal_planner()
    recipe = planner.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"success": True, "recipe": recipe}


@router.post("/receipt/scan")
async def scan_receipt(file: UploadFile = File(...)):
    """Scan and parse grocery receipt."""
    # TODO: Implement OCR receipt scanning
    return {
        "success": True,
        "message": "Receipt scanning coming soon",
        "items": []
    }


@router.get("/inventory")
async def get_inventory(user_id: str = "default"):
    """Get user's grocery inventory."""
    # TODO: Implement inventory storage
    return {
        "success": True,
        "user_id": user_id,
        "items": []
    }


@router.get("/stats")
async def get_grocery_stats(user_id: str = "default"):
    """Get grocery statistics."""
    return {
        "success": True,
        "total_items": 0,
        "expiring_soon": 0,
        "weekly_spending": 0
    }
