"""Meal planning service with health integration."""
import logging
from typing import List, Optional, Dict
from datetime import date, timedelta
import random

from app.models.grocery import (
    MealPlan, Recipe, NutritionalGoals, GroceryItem, ShoppingList
)

logger = logging.getLogger(__name__)


class MealPlanner:
    """Meal planning with health-based recommendations."""
    
    def __init__(self):
        self.recipes_db: List[Recipe] = []
        self._load_sample_recipes()
        
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Recipe]:
        """Get recipe by ID."""
        for r in self.recipes_db:
            if r.recipe_id == recipe_id:
                return r
        return None

    def get_all_recipes(self) -> List[Recipe]:
        """Return all recipes."""
        return self.recipes_db

    def _load_sample_recipes(self):
        """Load curated recipe database."""
        self.recipes_db = [
            # ── Breakfast ──
            Recipe(recipe_id="rec_001", name="Oatmeal with Berries", description="Heart-healthy breakfast packed with antioxidants", ingredients=["1 cup rolled oats", "1½ cups almond milk", "½ cup blueberries", "½ cup strawberries", "1 tbsp honey", "1 tbsp chia seeds"], instructions=["Bring almond milk to a boil", "Stir in oats, reduce heat, cook 5 min", "Top with berries, honey and chia seeds"], prep_time_minutes=5, cook_time_minutes=10, servings=1, calories_per_serving=310, protein_grams=9, carbs_grams=52, fat_grams=8, dietary_tags=["vegetarian", "heart-healthy", "high-fiber", "breakfast"], difficulty="easy"),
            Recipe(recipe_id="rec_002", name="Veggie Egg Scramble", description="Protein-rich scramble with fresh vegetables", ingredients=["3 eggs", "½ bell pepper diced", "¼ cup spinach", "¼ cup mushrooms sliced", "1 tbsp olive oil", "salt and pepper"], instructions=["Heat olive oil in a skillet over medium heat", "Sauté bell pepper and mushrooms 3 min", "Add spinach, cook 1 min", "Pour beaten eggs, stir gently until set"], prep_time_minutes=5, cook_time_minutes=8, servings=1, calories_per_serving=320, protein_grams=21, carbs_grams=6, fat_grams=24, dietary_tags=["high-protein", "low-carb", "gluten-free", "keto", "breakfast"], difficulty="easy"),
            Recipe(recipe_id="rec_003", name="Greek Yogurt Parfait", description="Quick, creamy parfait layered with granola and fruit", ingredients=["1 cup Greek yogurt", "¼ cup granola", "½ banana sliced", "2 tbsp honey", "1 tbsp walnuts"], instructions=["Layer yogurt in a glass", "Add granola and banana slices", "Drizzle with honey and top with walnuts"], prep_time_minutes=5, cook_time_minutes=0, servings=1, calories_per_serving=340, protein_grams=18, carbs_grams=48, fat_grams=10, dietary_tags=["vegetarian", "high-protein", "breakfast"], difficulty="easy"),
            Recipe(recipe_id="rec_004", name="Avocado Toast with Egg", description="Trendy, nutritious toast with healthy fats", ingredients=["2 slices whole grain bread", "1 ripe avocado", "2 eggs", "red pepper flakes", "lemon juice", "salt"], instructions=["Toast bread until golden", "Mash avocado with lemon juice and salt", "Fry or poach eggs", "Spread avocado on toast, top with egg and pepper flakes"], prep_time_minutes=5, cook_time_minutes=5, servings=1, calories_per_serving=420, protein_grams=18, carbs_grams=30, fat_grams=28, dietary_tags=["vegetarian", "high-protein", "breakfast"], difficulty="easy"),
            Recipe(recipe_id="rec_005", name="Masala Dosa", description="Crispy South Indian crepe with spiced potato filling", ingredients=["1 cup dosa batter", "2 potatoes boiled and mashed", "1 onion chopped", "1 tsp mustard seeds", "curry leaves", "turmeric", "green chilies", "oil"], instructions=["Heat oil, add mustard seeds and curry leaves", "Add onions, chilies, sauté until soft", "Mix in mashed potatoes and turmeric", "Spread batter on hot pan, cook until crispy, fill with potato mixture"], prep_time_minutes=10, cook_time_minutes=15, servings=2, calories_per_serving=290, protein_grams=7, carbs_grams=45, fat_grams=9, dietary_tags=["vegetarian", "vegan", "indian", "breakfast"], difficulty="medium"),
            # ── Lunch ──
            Recipe(recipe_id="rec_010", name="Grilled Chicken Salad", description="Protein-packed salad with grilled chicken breast", ingredients=["200g chicken breast", "4 cups mixed greens", "1 cup cherry tomatoes", "1 cucumber sliced", "¼ red onion", "2 tbsp olive oil", "1 tbsp lemon juice"], instructions=["Season and grill chicken 6 min per side", "Let rest 5 min, then slice", "Toss greens, tomatoes, cucumber and onion", "Top with chicken, dress with olive oil and lemon"], prep_time_minutes=10, cook_time_minutes=15, servings=2, calories_per_serving=350, protein_grams=35, carbs_grams=12, fat_grams=18, dietary_tags=["high-protein", "low-carb", "gluten-free", "lunch"], difficulty="easy"),
            Recipe(recipe_id="rec_011", name="Quinoa Buddha Bowl", description="Colorful nourishing bowl with plant-based protein", ingredients=["1 cup cooked quinoa", "½ cup chickpeas drained", "1 cup roasted sweet potato", "1 cup kale massaged", "½ avocado", "2 tbsp tahini dressing"], instructions=["Cook quinoa and let cool slightly", "Roast sweet potato cubes at 400°F for 25 min", "Arrange quinoa, chickpeas, sweet potato and kale in a bowl", "Top with avocado and drizzle tahini"], prep_time_minutes=10, cook_time_minutes=25, servings=1, calories_per_serving=520, protein_grams=18, carbs_grams=68, fat_grams=20, dietary_tags=["vegetarian", "vegan", "high-fiber", "lunch"], difficulty="easy"),
            Recipe(recipe_id="rec_012", name="Turkey Wrap", description="Light, satisfying wrap with lean protein", ingredients=["1 whole wheat tortilla", "100g sliced turkey", "lettuce leaves", "1 tomato sliced", "2 tbsp hummus", "¼ cucumber sliced"], instructions=["Spread hummus on tortilla", "Layer turkey, lettuce, tomato and cucumber", "Roll tightly, cut in half"], prep_time_minutes=5, cook_time_minutes=0, servings=1, calories_per_serving=340, protein_grams=28, carbs_grams=32, fat_grams=12, dietary_tags=["high-protein", "lunch"], difficulty="easy"),
            Recipe(recipe_id="rec_013", name="Dal Tadka with Rice", description="Comforting Indian lentil dish with tempered spices", ingredients=["1 cup toor dal", "1 onion chopped", "2 tomatoes chopped", "2 cloves garlic", "1 tsp cumin seeds", "1 tsp turmeric", "red chili powder", "ghee", "cilantro", "2 cups cooked rice"], instructions=["Pressure cook dal with turmeric until soft", "Heat ghee, add cumin seeds, garlic, onions", "Add tomatoes, cook until soft", "Add cooked dal, simmer 10 min", "Serve over steamed rice, garnish with cilantro"], prep_time_minutes=10, cook_time_minutes=25, servings=2, calories_per_serving=380, protein_grams=16, carbs_grams=62, fat_grams=8, dietary_tags=["vegetarian", "high-fiber", "indian", "lunch"], difficulty="easy"),
            Recipe(recipe_id="rec_014", name="Mediterranean Tuna Salad", description="Fresh tuna salad with olives and feta", ingredients=["1 can tuna drained", "1 cup cherry tomatoes halved", "½ cup kalamata olives", "¼ cup feta cheese", "½ red onion sliced", "2 tbsp olive oil", "1 tbsp red wine vinegar", "oregano"], instructions=["Combine tuna, tomatoes, olives, onion and feta", "Whisk olive oil, vinegar and oregano", "Toss salad with dressing", "Serve on a bed of mixed greens"], prep_time_minutes=10, cook_time_minutes=0, servings=2, calories_per_serving=310, protein_grams=26, carbs_grams=8, fat_grams=20, dietary_tags=["high-protein", "gluten-free", "mediterranean", "lunch"], difficulty="easy"),
            # ── Dinner ──
            Recipe(recipe_id="rec_020", name="Baked Salmon with Vegetables", description="Omega-3 rich salmon with roasted seasonal vegetables", ingredients=["2 salmon fillets", "2 cups broccoli florets", "1 cup carrots sliced", "2 tbsp olive oil", "1 lemon", "2 cloves garlic minced", "dill", "salt and pepper"], instructions=["Preheat oven to 400°F", "Place salmon and vegetables on a sheet pan", "Drizzle with olive oil, garlic, lemon juice", "Season and bake 18-20 min until salmon flakes easily"], prep_time_minutes=10, cook_time_minutes=20, servings=2, calories_per_serving=420, protein_grams=36, carbs_grams=14, fat_grams=24, dietary_tags=["high-protein", "gluten-free", "heart-healthy", "dinner"], difficulty="easy"),
            Recipe(recipe_id="rec_021", name="Chicken Stir-Fry", description="Quick, colorful stir-fry with fresh vegetables", ingredients=["300g chicken breast sliced", "1 bell pepper sliced", "1 cup broccoli", "1 carrot julienned", "3 tbsp soy sauce", "1 tbsp sesame oil", "1 tbsp ginger grated", "2 cloves garlic", "2 cups cooked brown rice"], instructions=["Heat sesame oil in wok over high heat", "Stir-fry chicken 5 min until cooked", "Add vegetables, stir-fry 3-4 min", "Add soy sauce and ginger, toss to coat", "Serve over brown rice"], prep_time_minutes=15, cook_time_minutes=12, servings=2, calories_per_serving=450, protein_grams=35, carbs_grams=48, fat_grams=12, dietary_tags=["high-protein", "dinner"], difficulty="easy"),
            Recipe(recipe_id="rec_022", name="Vegetable Pasta Primavera", description="Light pasta loaded with seasonal vegetables", ingredients=["200g whole wheat penne", "1 zucchini sliced", "1 cup cherry tomatoes", "1 cup asparagus cut", "¼ cup parmesan", "3 tbsp olive oil", "3 cloves garlic", "basil", "red pepper flakes"], instructions=["Cook pasta al dente, reserve ½ cup pasta water", "Sauté garlic in olive oil", "Add vegetables, cook 5 min", "Toss pasta with vegetables, add pasta water as needed", "Top with parmesan and fresh basil"], prep_time_minutes=10, cook_time_minutes=15, servings=2, calories_per_serving=410, protein_grams=16, carbs_grams=56, fat_grams=14, dietary_tags=["vegetarian", "dinner"], difficulty="easy"),
            Recipe(recipe_id="rec_023", name="Paneer Tikka Masala", description="Rich, creamy Indian paneer curry", ingredients=["250g paneer cubed", "1 cup tomato puree", "½ cup heavy cream", "1 onion chopped", "2 cloves garlic", "1 inch ginger", "garam masala", "turmeric", "chili powder", "kasuri methi", "butter", "naan bread"], instructions=["Marinate paneer in yogurt and spices, grill or pan-fry", "Sauté onions, garlic, ginger until golden", "Add tomato puree, cook 10 min", "Add spices, cream and grilled paneer", "Simmer 5 min, garnish with kasuri methi", "Serve with naan"], prep_time_minutes=20, cook_time_minutes=25, servings=3, calories_per_serving=460, protein_grams=18, carbs_grams=22, fat_grams=34, dietary_tags=["vegetarian", "indian", "dinner"], difficulty="medium"),
            Recipe(recipe_id="rec_024", name="Grilled Shrimp Tacos", description="Fresh, zesty tacos with grilled shrimp", ingredients=["300g shrimp peeled", "6 corn tortillas", "1 cup cabbage shredded", "1 avocado sliced", "lime juice", "chipotle mayo", "cilantro", "cumin", "paprika"], instructions=["Season shrimp with cumin, paprika, salt", "Grill shrimp 2-3 min per side", "Warm tortillas", "Assemble with cabbage, avocado, shrimp", "Drizzle chipotle mayo and lime juice, top with cilantro"], prep_time_minutes=15, cook_time_minutes=8, servings=2, calories_per_serving=390, protein_grams=30, carbs_grams=32, fat_grams=16, dietary_tags=["high-protein", "gluten-free", "dinner"], difficulty="easy"),
            Recipe(recipe_id="rec_025", name="Beef and Broccoli", description="Classic stir-fry with tender beef", ingredients=["300g flank steak sliced thin", "3 cups broccoli florets", "3 tbsp soy sauce", "1 tbsp oyster sauce", "1 tbsp cornstarch", "2 cloves garlic", "1 inch ginger", "sesame oil", "2 cups jasmine rice"], instructions=["Marinate beef in soy sauce and cornstarch 15 min", "Heat oil in wok, sear beef 2 min, remove", "Stir-fry broccoli with garlic and ginger 3 min", "Return beef, add oyster sauce, toss", "Serve over jasmine rice"], prep_time_minutes=20, cook_time_minutes=10, servings=2, calories_per_serving=480, protein_grams=32, carbs_grams=52, fat_grams=14, dietary_tags=["high-protein", "dinner"], difficulty="medium"),
            # ── Snacks / Light ──
            Recipe(recipe_id="rec_030", name="Hummus with Veggie Sticks", description="Classic hummus with crunchy fresh vegetables", ingredients=["1 can chickpeas", "2 tbsp tahini", "1 lemon juiced", "2 cloves garlic", "2 tbsp olive oil", "carrots", "celery", "bell pepper strips"], instructions=["Blend chickpeas, tahini, lemon juice, garlic and olive oil until smooth", "Cut vegetables into sticks", "Serve hummus with veggie sticks"], prep_time_minutes=10, cook_time_minutes=0, servings=4, calories_per_serving=180, protein_grams=7, carbs_grams=20, fat_grams=9, dietary_tags=["vegetarian", "vegan", "gluten-free", "snack"], difficulty="easy"),
            Recipe(recipe_id="rec_031", name="Protein Smoothie", description="Post-workout smoothie with banana and protein", ingredients=["1 banana", "1 cup almond milk", "1 scoop protein powder", "1 tbsp peanut butter", "½ cup ice", "1 tbsp honey"], instructions=["Add all ingredients to blender", "Blend until smooth", "Pour and serve immediately"], prep_time_minutes=3, cook_time_minutes=0, servings=1, calories_per_serving=350, protein_grams=25, carbs_grams=42, fat_grams=10, dietary_tags=["high-protein", "vegetarian", "snack", "breakfast"], difficulty="easy"),
        ]
    
    async def generate_meal_plan(
        self,
        user_id: str,
        start_date: date,
        days: int,
        nutritional_goals: Optional[NutritionalGoals] = None,
        preferences: Optional[Dict] = None
    ) -> List[MealPlan]:
        """Generate meal plan based on health goals and preferences."""
        meal_plans = []
        
        # Get user's health data if available
        if not nutritional_goals:
            nutritional_goals = await self._get_nutritional_goals(user_id)
        
        for day_offset in range(days):
            plan_date = start_date + timedelta(days=day_offset)
            
            # Select meals based on nutritional goals
            breakfast = self._select_meal("breakfast", nutritional_goals, preferences)
            lunch = self._select_meal("lunch", nutritional_goals, preferences)
            dinner = self._select_meal("dinner", nutritional_goals, preferences)
            
            total_calories = (
                (breakfast.calories_per_serving if breakfast else 0) +
                (lunch.calories_per_serving if lunch else 0) +
                (dinner.calories_per_serving if dinner else 0)
            )
            
            meal_plan = MealPlan(
                date=plan_date,
                breakfast=breakfast.name if breakfast else None,
                breakfast_calories=breakfast.calories_per_serving if breakfast else None,
                breakfast_recipe_url=f"/recipes/{breakfast.recipe_id}" if breakfast else None,
                lunch=lunch.name if lunch else None,
                lunch_calories=lunch.calories_per_serving if lunch else None,
                lunch_recipe_url=f"/recipes/{lunch.recipe_id}" if lunch else None,
                dinner=dinner.name if dinner else None,
                dinner_calories=dinner.calories_per_serving if dinner else None,
                dinner_recipe_url=f"/recipes/{dinner.recipe_id}" if dinner else None,
                total_calories=total_calories,
                nutritional_goals_met=self._check_goals_met(total_calories, nutritional_goals)
            )
            
            meal_plans.append(meal_plan)
        
        return meal_plans
    
    async def suggest_recipes(
        self,
        available_ingredients: List[str],
        nutritional_goals: Optional[NutritionalGoals] = None,
        meal_type: Optional[str] = None
    ) -> List[Recipe]:
        """Suggest recipes based on available ingredients."""
        matching_recipes = []
        
        for recipe in self.recipes_db:
            # Check ingredient match
            ingredients_available = sum(
                1 for ing in recipe.ingredients 
                if any(avail.lower() in ing.lower() for avail in available_ingredients)
            )
            
            match_percentage = ingredients_available / len(recipe.ingredients)
            
            if match_percentage >= 0.6:  # At least 60% ingredients available
                matching_recipes.append(recipe)
        
        # Filter by nutritional goals
        if nutritional_goals:
            matching_recipes = self._filter_by_nutrition(matching_recipes, nutritional_goals)
        
        # Sort by match percentage and rating
        matching_recipes.sort(key=lambda r: len(r.ingredients), reverse=False)
        
        return matching_recipes[:10]
    
    async def generate_shopping_list(
        self,
        meal_plans: List[MealPlan],
        current_inventory: List[GroceryItem]
    ) -> ShoppingList:
        """Generate shopping list from meal plans."""
        needed_items = {}
        
        # Collect all ingredients from meal plans
        for plan in meal_plans:
            for meal_name in [plan.breakfast, plan.lunch, plan.dinner]:
                if meal_name:
                    recipe = self._find_recipe_by_name(meal_name)
                    if recipe:
                        for ingredient in recipe.ingredients:
                            if ingredient not in needed_items:
                                needed_items[ingredient] = {
                                    "name": ingredient,
                                    "quantity": 1,
                                    "unit": "item",
                                    "category": self._categorize_ingredient(ingredient),
                                    "estimated_price": self._estimate_price(ingredient)
                                }
                            else:
                                needed_items[ingredient]["quantity"] += 1
        
        # Remove items already in inventory
        for item in current_inventory:
            if item.name in needed_items:
                del needed_items[item.name]
        
        items_list = list(needed_items.values())
        total_cost = sum(item["estimated_price"] * item["quantity"] for item in items_list)
        
        # Group by store
        stores = list(set(self._suggest_store(item["category"]) for item in items_list))
        
        shopping_list = ShoppingList(
            list_id=f"list_{int(date.today().timestamp())}",
            user_id="default",
            created_date=date.today(),
            items=items_list,
            total_estimated_cost=total_cost,
            stores_to_visit=stores
        )
        
        return shopping_list
    
    async def _get_nutritional_goals(self, user_id: str) -> NutritionalGoals:
        """Get user's nutritional goals from health reports."""
        # TODO: Integrate with health reports to extract recommendations
        # For now, return default goals
        return NutritionalGoals(
            user_id=user_id,
            daily_calories=2000,
            protein_grams=50,
            carbs_grams=250,
            fat_grams=70,
            fiber_grams=25,
            sodium_mg=2300,
            sugar_grams=50,
            dietary_restrictions=[],
            health_conditions=[],
            recommendations=[]
        )
    
    def _select_meal(
        self,
        meal_type: str,
        goals: NutritionalGoals,
        preferences: Optional[Dict]
    ) -> Optional[Recipe]:
        """Select appropriate meal based on goals and meal type."""
        suitable_recipes = self.recipes_db.copy()
        
        # Prefer recipes tagged for this meal type
        tagged = [r for r in suitable_recipes if meal_type in r.dietary_tags]
        if tagged:
            suitable_recipes = tagged
        
        # Filter by dietary restrictions
        if goals.dietary_restrictions:
            suitable_recipes = [
                r for r in suitable_recipes
                if not any(restriction in r.dietary_tags for restriction in goals.dietary_restrictions)
            ]
        
        # Filter by preferences
        if preferences and preferences.get("avoid"):
            avoid_ingredients = preferences["avoid"]
            suitable_recipes = [
                r for r in suitable_recipes
                if not any(ing in r.ingredients for ing in avoid_ingredients)
            ]

        # Filter vegetarian/vegan if requested
        if preferences and preferences.get("diet"):
            diet = preferences["diet"]
            if diet in ("vegetarian", "vegan"):
                suitable_recipes = [r for r in suitable_recipes if diet in r.dietary_tags]
        
        if not suitable_recipes:
            return None
        
        return random.choice(suitable_recipes)
    
    def _check_goals_met(self, total_calories: int, goals: NutritionalGoals) -> bool:
        """Check if nutritional goals are met."""
        return abs(total_calories - goals.daily_calories) <= goals.daily_calories * 0.1
    
    def _filter_by_nutrition(
        self,
        recipes: List[Recipe],
        goals: NutritionalGoals
    ) -> List[Recipe]:
        """Filter recipes by nutritional goals."""
        filtered = []
        
        for recipe in recipes:
            # Check if recipe fits within goals
            if recipe.calories_per_serving <= goals.daily_calories / 3:  # Rough estimate per meal
                filtered.append(recipe)
        
        return filtered
    
    def _find_recipe_by_name(self, name: str) -> Optional[Recipe]:
        """Find recipe by name."""
        for recipe in self.recipes_db:
            if recipe.name == name:
                return recipe
        return None
    
    def _categorize_ingredient(self, ingredient: str) -> str:
        """Categorize ingredient."""
        categories = {
            "produce": ["lettuce", "tomato", "cucumber", "berries", "apple"],
            "meat": ["chicken", "beef", "pork", "fish"],
            "dairy": ["milk", "cheese", "yogurt"],
            "pantry": ["rice", "pasta", "oats", "flour"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in ingredient.lower() for keyword in keywords):
                return category
        
        return "other"
    
    def _estimate_price(self, ingredient: str) -> float:
        """Estimate ingredient price."""
        # Simple price estimation
        price_map = {
            "produce": 3.0,
            "meat": 8.0,
            "dairy": 4.0,
            "pantry": 2.0,
            "other": 3.0
        }
        category = self._categorize_ingredient(ingredient)
        return price_map.get(category, 3.0)
    
    def _suggest_store(self, category: str) -> str:
        """Suggest store for category."""
        store_map = {
            "produce": "Whole Foods",
            "meat": "Butcher Shop",
            "dairy": "Grocery Store",
            "pantry": "Grocery Store",
            "other": "Grocery Store"
        }
        return store_map.get(category, "Grocery Store")


# Singleton instance
_meal_planner: Optional[MealPlanner] = None


def get_meal_planner() -> MealPlanner:
    """Get meal planner singleton."""
    global _meal_planner
    if _meal_planner is None:
        _meal_planner = MealPlanner()
    return _meal_planner
