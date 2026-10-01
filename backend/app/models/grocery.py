"""Grocery tracking and meal planning models."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


class GroceryItem(BaseModel):
    """Grocery item in inventory."""
    item_id: str
    name: str
    category: str  # produce, dairy, meat, pantry, etc.
    quantity: float
    unit: str  # lbs, oz, count, etc.
    purchase_date: date
    expiration_date: Optional[date] = None
    price: float
    store: str
    barcode: Optional[str] = None
    image_url: Optional[str] = None


class Receipt(BaseModel):
    """Scanned receipt."""
    receipt_id: str
    user_id: str
    store: str
    purchase_date: date
    total_amount: float
    items: List[GroceryItem]
    image_url: Optional[str] = None
    parsed_date: datetime


class MealPlan(BaseModel):
    """Meal plan for a day."""
    date: date
    breakfast: Optional[str] = None
    breakfast_calories: Optional[int] = None
    breakfast_recipe_url: Optional[str] = None
    lunch: Optional[str] = None
    lunch_calories: Optional[int] = None
    lunch_recipe_url: Optional[str] = None
    dinner: Optional[str] = None
    dinner_calories: Optional[int] = None
    dinner_recipe_url: Optional[str] = None
    snacks: List[str] = []
    total_calories: int = 0
    nutritional_goals_met: bool = False


class Recipe(BaseModel):
    """Recipe information."""
    recipe_id: str
    name: str
    description: str
    ingredients: List[str]
    instructions: List[str]
    prep_time_minutes: int
    cook_time_minutes: int
    servings: int
    calories_per_serving: int
    protein_grams: float
    carbs_grams: float
    fat_grams: float
    dietary_tags: List[str] = []  # vegetarian, vegan, gluten-free, etc.
    difficulty: str = "medium"
    image_url: Optional[str] = None
    source_url: Optional[str] = None


class NutritionalGoals(BaseModel):
    """User's nutritional goals based on health reports."""
    user_id: str
    daily_calories: int
    protein_grams: float
    carbs_grams: float
    fat_grams: float
    fiber_grams: float
    sodium_mg: float
    sugar_grams: float
    dietary_restrictions: List[str] = []
    health_conditions: List[str] = []  # from lab reports
    recommendations: List[str] = []


class ShoppingList(BaseModel):
    """Shopping list generated from meal plans."""
    list_id: str
    user_id: str
    created_date: datetime
    items: List[dict]  # {name, quantity, unit, category, estimated_price}
    total_estimated_cost: float
    stores_to_visit: List[str]
    optimized_route: Optional[str] = None
