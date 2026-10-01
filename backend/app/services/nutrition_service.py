"""
Nutrition Service - AI-Powered Meal Planning and Dietary Recommendations
Provides personalized meal plans based on age, gender, health goals, and dietary preferences
"""
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.llm_client import extract_json, generate as llm_generate

logger = logging.getLogger(__name__)


class NutritionService:
    """
    AI-powered nutrition service with:
    - Personalized meal plans
    - Age/gender-based recommendations
    - Health goal-specific diets
    - Dietary restriction support
    - Calorie and macro tracking
    """
    
    async def get_meal_plan(
        self,
        age: int,
        gender: str,
        health_goals: Optional[List[str]] = None,
        dietary_preferences: Optional[List[str]] = None,
        cuisine_preferences: Optional[str] = None,
        allergies: Optional[List[str]] = None,
        ollama_host: str = None,
        ollama_model: str = None
    ) -> Dict[str, Any]:
        """
        Get personalized meal plan based on user profile using AI.
        
        Args:
            age: User age
            gender: User gender (male/female/other)
            health_goals: List of goals (weight_loss, muscle_gain, heart_health, etc.)
            dietary_preferences: List of preferences (vegetarian, vegan, keto, etc.)
            cuisine_preferences: Preferred cuisines (e.g., "Telugu, South Indian")
            allergies: List of allergies
            ollama_host: Ollama API host for AI recommendations
            ollama_model: Model to use
        """
        
        # Determine calorie needs based on age and gender
        calorie_needs = self._calculate_calorie_needs(age, gender, health_goals)
        
        # ALWAYS try to use LLM for personalized meal plans
        ai_meal_plan = None
        if ollama_host and ollama_model:
            try:
                ai_meal_plan = await self._generate_ai_meal_plan(
                    age, gender, health_goals, dietary_preferences, cuisine_preferences, 
                    allergies, calorie_needs, ollama_host, ollama_model
                )
                logger.info(f"AI meal plan generated for cuisine: {cuisine_preferences}")
            except Exception as e:
                logger.error(f"Error generating AI meal plan: {e}")
        
        # Use AI-generated plan if available, otherwise fall back to default
        if ai_meal_plan:
            meal_plan = ai_meal_plan
            meal_plan["ai_generated"] = True
        else:
            meal_plan = self._generate_default_meal_plan(
                age, gender, health_goals, dietary_preferences, cuisine_preferences, allergies, calorie_needs
            )
            meal_plan["ai_generated"] = False
        
        return {
            "success": True,
            "meal_plan": meal_plan,
            "calorie_target": calorie_needs,
            "cuisine_preferences": cuisine_preferences,
            "generated_at": datetime.now().isoformat(),
            "powered_by": "AI" if meal_plan.get("ai_generated") else "Default"
        }
    
    def _calculate_calorie_needs(
        self,
        age: int,
        gender: str,
        health_goals: Optional[List[str]]
    ) -> int:
        """Calculate daily calorie needs."""
        
        # Base calorie needs by age and gender
        if age <= 5:
            base_calories = 1200
        elif age <= 12:
            base_calories = 1600 if gender.lower() == "female" else 1800
        elif age <= 17:
            base_calories = 2000 if gender.lower() == "female" else 2400
        elif age <= 64:
            base_calories = 2000 if gender.lower() == "female" else 2500
        else:
            base_calories = 1800 if gender.lower() == "female" else 2200
        
        # Adjust for health goals
        if health_goals:
            if "weight_loss" in health_goals:
                base_calories = int(base_calories * 0.85)
            elif "muscle_gain" in health_goals:
                base_calories = int(base_calories * 1.15)
        
        return base_calories
    
    def _generate_default_meal_plan(
        self,
        age: int,
        gender: str,
        health_goals: Optional[List[str]],
        dietary_preferences: Optional[List[str]],
        cuisine_preferences: Optional[str],
        allergies: Optional[List[str]],
        calorie_needs: int
    ) -> Dict[str, Any]:
        """Generate default meal plan with 3-4 options per meal."""
        
        is_vegetarian = dietary_preferences and "vegetarian" in dietary_preferences
        is_vegan = dietary_preferences and "vegan" in dietary_preferences
        is_keto = dietary_preferences and "keto" in dietary_preferences
        
        # Check for cuisine preferences
        is_indian = cuisine_preferences and "indian" in cuisine_preferences.lower()
        is_south_indian = cuisine_preferences and "south indian" in cuisine_preferences.lower()
        is_mediterranean = cuisine_preferences and "mediterranean" in cuisine_preferences.lower()
        is_asian = cuisine_preferences and "asian" in cuisine_preferences.lower()
        
        # Breakfast options
        breakfast_options = []
        if is_south_indian or is_indian:
            breakfast_options = [
                {
                    "name": "Idli with Sambar and Coconut Chutney",
                    "calories": 320,
                    "protein": 12,
                    "carbs": 58,
                    "fat": 6,
                    "ingredients": ["Rice idli", "Sambar (lentil curry)", "Coconut chutney", "Curry leaves"],
                    "prep_time": "20 min"
                },
                {
                    "name": "Masala Dosa with Potato Filling",
                    "calories": 380,
                    "protein": 10,
                    "carbs": 65,
                    "fat": 10,
                    "ingredients": ["Rice dosa", "Spiced potato filling", "Sambar", "Chutney"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Upma with Vegetables",
                    "calories": 290,
                    "protein": 8,
                    "carbs": 48,
                    "fat": 8,
                    "ingredients": ["Semolina", "Mixed vegetables", "Mustard seeds", "Curry leaves", "Peanuts"],
                    "prep_time": "15 min"
                },
                {
                    "name": "Poha (Flattened Rice) with Peanuts",
                    "calories": 310,
                    "protein": 9,
                    "carbs": 52,
                    "fat": 9,
                    "ingredients": ["Flattened rice", "Peanuts", "Turmeric", "Curry leaves", "Lemon"],
                    "prep_time": "15 min"
                }
            ]
        elif is_vegan:
            breakfast_options = [
                {
                    "name": "Oatmeal with Berries and Almond Butter",
                    "calories": 350,
                    "protein": 12,
                    "carbs": 52,
                    "fat": 12,
                    "ingredients": ["Oats", "Blueberries", "Almond butter", "Chia seeds"],
                    "prep_time": "10 min"
                },
                {
                    "name": "Tofu Scramble with Vegetables",
                    "calories": 320,
                    "protein": 18,
                    "carbs": 25,
                    "fat": 16,
                    "ingredients": ["Tofu", "Spinach", "Tomatoes", "Turmeric"],
                    "prep_time": "15 min"
                },
                {
                    "name": "Smoothie Bowl with Granola",
                    "calories": 380,
                    "protein": 10,
                    "carbs": 58,
                    "fat": 14,
                    "ingredients": ["Banana", "Berries", "Plant milk", "Granola", "Seeds"],
                    "prep_time": "10 min"
                }
            ]
        elif is_keto:
            breakfast_options = [
                {
                    "name": "Eggs with Avocado and Bacon",
                    "calories": 450,
                    "protein": 28,
                    "carbs": 8,
                    "fat": 36,
                    "ingredients": ["Eggs", "Avocado", "Bacon", "Cheese"],
                    "prep_time": "15 min"
                },
                {
                    "name": "Greek Yogurt with Nuts and Seeds",
                    "calories": 380,
                    "protein": 22,
                    "carbs": 12,
                    "fat": 28,
                    "ingredients": ["Full-fat yogurt", "Almonds", "Walnuts", "Chia seeds"],
                    "prep_time": "5 min"
                },
                {
                    "name": "Keto Pancakes with Butter",
                    "calories": 420,
                    "protein": 20,
                    "carbs": 6,
                    "fat": 36,
                    "ingredients": ["Almond flour", "Eggs", "Cream cheese", "Butter"],
                    "prep_time": "20 min"
                }
            ]
        else:
            breakfast_options = [
                {
                    "name": "Whole Grain Toast with Eggs and Avocado",
                    "calories": 400,
                    "protein": 20,
                    "carbs": 35,
                    "fat": 18,
                    "ingredients": ["Whole grain bread", "Eggs", "Avocado", "Tomatoes"],
                    "prep_time": "15 min"
                },
                {
                    "name": "Greek Yogurt Parfait with Granola",
                    "calories": 350,
                    "protein": 18,
                    "carbs": 45,
                    "fat": 10,
                    "ingredients": ["Greek yogurt", "Granola", "Berries", "Honey"],
                    "prep_time": "5 min"
                },
                {
                    "name": "Protein Smoothie with Banana",
                    "calories": 380,
                    "protein": 25,
                    "carbs": 48,
                    "fat": 8,
                    "ingredients": ["Protein powder", "Banana", "Milk", "Peanut butter"],
                    "prep_time": "5 min"
                },
                {
                    "name": "Omelette with Vegetables and Cheese",
                    "calories": 420,
                    "protein": 28,
                    "carbs": 12,
                    "fat": 28,
                    "ingredients": ["Eggs", "Bell peppers", "Spinach", "Cheese"],
                    "prep_time": "15 min"
                }
            ]
        
        # Lunch options
        lunch_options = []
        if is_vegan:
            lunch_options = [
                {
                    "name": "Quinoa Buddha Bowl",
                    "calories": 520,
                    "protein": 18,
                    "carbs": 68,
                    "fat": 18,
                    "ingredients": ["Quinoa", "Chickpeas", "Kale", "Tahini", "Vegetables"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Lentil Soup with Whole Grain Bread",
                    "calories": 480,
                    "protein": 22,
                    "carbs": 72,
                    "fat": 10,
                    "ingredients": ["Lentils", "Vegetables", "Spices", "Bread"],
                    "prep_time": "30 min"
                },
                {
                    "name": "Veggie Wrap with Hummus",
                    "calories": 450,
                    "protein": 16,
                    "carbs": 58,
                    "fat": 16,
                    "ingredients": ["Whole wheat wrap", "Hummus", "Vegetables", "Sprouts"],
                    "prep_time": "10 min"
                }
            ]
        elif is_keto:
            lunch_options = [
                {
                    "name": "Grilled Chicken Salad with Olive Oil",
                    "calories": 550,
                    "protein": 42,
                    "carbs": 10,
                    "fat": 38,
                    "ingredients": ["Chicken breast", "Mixed greens", "Olive oil", "Cheese"],
                    "prep_time": "20 min"
                },
                {
                    "name": "Salmon with Asparagus and Butter",
                    "calories": 580,
                    "protein": 45,
                    "carbs": 8,
                    "fat": 42,
                    "ingredients": ["Salmon", "Asparagus", "Butter", "Lemon"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Beef Lettuce Wraps",
                    "calories": 520,
                    "protein": 38,
                    "carbs": 12,
                    "fat": 36,
                    "ingredients": ["Ground beef", "Lettuce", "Cheese", "Avocado"],
                    "prep_time": "20 min"
                }
            ]
        else:
            lunch_options = [
                {
                    "name": "Grilled Chicken with Brown Rice and Vegetables",
                    "calories": 550,
                    "protein": 42,
                    "carbs": 58,
                    "fat": 12,
                    "ingredients": ["Chicken breast", "Brown rice", "Broccoli", "Carrots"],
                    "prep_time": "30 min"
                },
                {
                    "name": "Turkey and Avocado Sandwich",
                    "calories": 480,
                    "protein": 32,
                    "carbs": 48,
                    "fat": 16,
                    "ingredients": ["Whole grain bread", "Turkey", "Avocado", "Lettuce"],
                    "prep_time": "10 min"
                },
                {
                    "name": "Salmon Salad with Quinoa",
                    "calories": 520,
                    "protein": 38,
                    "carbs": 42,
                    "fat": 20,
                    "ingredients": ["Salmon", "Quinoa", "Mixed greens", "Olive oil"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Pasta with Marinara and Lean Ground Turkey",
                    "calories": 580,
                    "protein": 35,
                    "carbs": 72,
                    "fat": 14,
                    "ingredients": ["Whole wheat pasta", "Ground turkey", "Marinara", "Vegetables"],
                    "prep_time": "25 min"
                }
            ]
        
        # Dinner options
        dinner_options = []
        if is_vegan:
            dinner_options = [
                {
                    "name": "Stir-Fried Tofu with Vegetables and Rice",
                    "calories": 520,
                    "protein": 22,
                    "carbs": 68,
                    "fat": 16,
                    "ingredients": ["Tofu", "Brown rice", "Mixed vegetables", "Soy sauce"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Black Bean Tacos with Guacamole",
                    "calories": 480,
                    "protein": 18,
                    "carbs": 62,
                    "fat": 18,
                    "ingredients": ["Black beans", "Corn tortillas", "Avocado", "Salsa"],
                    "prep_time": "20 min"
                },
                {
                    "name": "Vegetable Curry with Chickpeas",
                    "calories": 550,
                    "protein": 20,
                    "carbs": 72,
                    "fat": 18,
                    "ingredients": ["Chickpeas", "Coconut milk", "Vegetables", "Curry spices"],
                    "prep_time": "30 min"
                }
            ]
        elif is_keto:
            dinner_options = [
                {
                    "name": "Ribeye Steak with Cauliflower Mash",
                    "calories": 680,
                    "protein": 52,
                    "carbs": 12,
                    "fat": 48,
                    "ingredients": ["Ribeye", "Cauliflower", "Butter", "Cream"],
                    "prep_time": "30 min"
                },
                {
                    "name": "Baked Salmon with Zucchini Noodles",
                    "calories": 580,
                    "protein": 48,
                    "carbs": 10,
                    "fat": 38,
                    "ingredients": ["Salmon", "Zucchini", "Olive oil", "Garlic"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Chicken Thighs with Brussels Sprouts",
                    "calories": 620,
                    "protein": 45,
                    "carbs": 14,
                    "fat": 42,
                    "ingredients": ["Chicken thighs", "Brussels sprouts", "Bacon", "Butter"],
                    "prep_time": "35 min"
                }
            ]
        else:
            dinner_options = [
                {
                    "name": "Grilled Salmon with Sweet Potato and Broccoli",
                    "calories": 580,
                    "protein": 42,
                    "carbs": 52,
                    "fat": 18,
                    "ingredients": ["Salmon", "Sweet potato", "Broccoli", "Olive oil"],
                    "prep_time": "30 min"
                },
                {
                    "name": "Chicken Stir-Fry with Brown Rice",
                    "calories": 550,
                    "protein": 38,
                    "carbs": 62,
                    "fat": 14,
                    "ingredients": ["Chicken", "Brown rice", "Mixed vegetables", "Soy sauce"],
                    "prep_time": "25 min"
                },
                {
                    "name": "Lean Beef with Roasted Vegetables",
                    "calories": 620,
                    "protein": 45,
                    "carbs": 48,
                    "fat": 22,
                    "ingredients": ["Lean beef", "Potatoes", "Carrots", "Green beans"],
                    "prep_time": "40 min"
                },
                {
                    "name": "Turkey Meatballs with Whole Wheat Pasta",
                    "calories": 580,
                    "protein": 42,
                    "carbs": 68,
                    "fat": 14,
                    "ingredients": ["Ground turkey", "Whole wheat pasta", "Marinara", "Vegetables"],
                    "prep_time": "35 min"
                }
            ]
        
        # Snack options
        snack_options = [
            {"name": "Apple with Almond Butter", "calories": 200, "prep_time": "2 min"},
            {"name": "Greek Yogurt with Berries", "calories": 150, "prep_time": "2 min"},
            {"name": "Handful of Mixed Nuts", "calories": 180, "prep_time": "1 min"},
            {"name": "Hummus with Carrot Sticks", "calories": 120, "prep_time": "5 min"}
        ]
        
        return {
            "breakfast": breakfast_options,
            "lunch": lunch_options,
            "dinner": dinner_options,
            "snacks": snack_options,
            "dietary_info": {
                "is_vegetarian": is_vegetarian,
                "is_vegan": is_vegan,
                "is_keto": is_keto,
                "allergies": allergies or []
            }
        }
    
    async def _generate_ai_meal_plan(
        self,
        age: int,
        gender: str,
        health_goals: Optional[List[str]],
        dietary_preferences: Optional[List[str]],
        cuisine_preferences: Optional[str],
        allergies: Optional[List[str]],
        calorie_needs: int,
        ollama_host: str,
        ollama_model: str
    ) -> Optional[Dict[str, Any]]:
        """Generate personalized AI meal plan based on cuisine preferences."""
        
        cuisine = cuisine_preferences or "balanced international"
        diet_prefs = ', '.join(dietary_preferences or ['balanced'])
        goals = ', '.join(health_goals or ['general health'])
        allergy_list = ', '.join(allergies or ['none'])
        
        prompt = f"""Generate a personalized meal plan for someone with these requirements:

- Age: {age} years old
- Gender: {gender}
- Daily Calorie Target: {calorie_needs} calories
- Cuisine Preference: {cuisine}
- Dietary Preferences: {diet_prefs}
- Health Goals: {goals}
- Allergies/Restrictions: {allergy_list}

Generate 3 options each for breakfast, lunch, and dinner that match the cuisine preference.
For each meal provide: name, approximate calories, protein(g), carbs(g), fat(g), and 4-5 key ingredients.

Format your response EXACTLY as JSON (no markdown, no explanation):
{{
  "breakfast": [
    {{"name": "Meal Name", "calories": 350, "protein": 15, "carbs": 45, "fat": 12, "ingredients": ["ingredient1", "ingredient2", "ingredient3", "ingredient4"]}}
  ],
  "lunch": [...],
  "dinner": [...]
}}

IMPORTANT: Return ONLY the JSON object, no other text."""

        try:
            ai_response = await llm_generate(
                prompt, task="fast", temperature=0.3, timeout=60, json_mode=True,
            )

            if ai_response:
                meal_plan = extract_json(ai_response)
                if isinstance(meal_plan, dict) and "breakfast" in meal_plan and "lunch" in meal_plan and "dinner" in meal_plan:
                    logger.info(f"Successfully parsed AI meal plan for {cuisine}")
                    return meal_plan
                logger.warning("AI response was not valid JSON, falling back to default")
        except Exception as e:
            logger.error(f"Error generating AI meal plan: {e}")

        return None
    
    async def _get_ai_meal_recommendations(
        self,
        age: int,
        gender: str,
        health_goals: Optional[List[str]],
        dietary_preferences: Optional[List[str]],
        allergies: Optional[List[str]],
        ollama_host: str,
        ollama_model: str
    ) -> str:
        """Get AI-powered meal recommendations."""
        
        prompt = f"""Provide personalized nutrition advice for:
Age: {age}
Gender: {gender}
Health Goals: {', '.join(health_goals or ['general health'])}
Dietary Preferences: {', '.join(dietary_preferences or ['none'])}
Allergies: {', '.join(allergies or ['none'])}

Provide:
1. Key nutritional priorities
2. Foods to emphasize
3. Foods to limit
4. Hydration tips
5. Meal timing suggestions

Be concise and practical."""

        try:
            text = await llm_generate(
                prompt, task="fast", temperature=0.3, timeout=30,
            )
            if text:
                return text
        except Exception as e:
            logger.error(f"Error getting AI recommendations: {e}")

        return "Focus on balanced meals with adequate protein, healthy fats, and complex carbohydrates."


# Singleton instance
_nutrition_service: Optional[NutritionService] = None


def get_nutrition_service() -> NutritionService:
    """Get nutrition service instance."""
    global _nutrition_service
    if _nutrition_service is None:
        _nutrition_service = NutritionService()
    return _nutrition_service
