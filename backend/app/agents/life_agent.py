"""
Life Agent - Llama 3.3 70B for lifestyle management.

Handles nutrition, travel, shopping, wellness, and daily life recommendations.
Uses the largest model for nuanced, context-rich lifestyle advice.
"""

from typing import Dict, Any, Optional, List
import logging
import json

from app.agents.base_agent import BaseAgent
from app.integrations.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Life Agent of Omni-PLA, an elite Personal Life Assistant.

Your specialties:
1. **Nutrition**: Weekly cravings → healthy swaps OR premium restaurant picks. 
   Follow Clean 15/Dirty Dozen rules. Track macros.
2. **Shopping**: Quality-first approach. EWG pesticide guide compliance.
   Dirty Dozen → always organic. Clean 15 → conventional OK.
   Budget tiers: Elite-Organic, Balanced, Budget-Conscious.
3. **Travel**: Real-time flight analysis with personal financial impact.
   Always contextualize cost as % of monthly income/trading profits.
4. **Wellness**: Exercise, sleep, stress management recommendations.

Rules:
- Never compromise on food quality for cost
- Always provide specific, actionable recommendations
- Include nutritional data (calories, protein, carbs, fats) for food items
- For shopping, always note if item is on Dirty Dozen list
- For travel, always include personal impact analysis"""


class LifeAgent(BaseAgent):
    """
    Lifestyle management agent using Llama 3.3 70B.
    Handles nutrition, travel, shopping, and wellness with deep context.
    """

    def __init__(self):
        super().__init__(
            name="LifeAgent",
            model="llama3.3:70b-instruct-q4_K_M",
            temperature=0.6,
        )
        self.ollama = OllamaClient.for_role("life")

    async def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate lifestyle task input."""
        return "type" in task

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the appropriate lifestyle handler."""
        task_type = task.get("type")

        handlers = {
            "nutrition_swap": self.suggest_healthy_swap,
            "meal_plan": self.create_meal_plan,
            "shopping_advice": self.shopping_advice,
            "travel_impact": self.analyze_travel_impact,
            "wellness_plan": self.create_wellness_plan,
            "craving_response": self.handle_craving,
        }

        handler = handlers.get(task_type)
        if handler:
            return await handler(task)

        return {"success": False, "error": f"Unknown life task: {task_type}"}

    async def handle_craving(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle weekly cravings with two paths:
        1. Healthy Swap (organic home version)
        2. Premium Indulgence (local high-end restaurant)
        """
        craving = task.get("craving", "")
        dietary_restrictions = task.get("dietary_restrictions", [])
        location = task.get("location", "Charlotte, NC")

        prompt = f"""The user is craving: "{craving}"
Dietary restrictions: {', '.join(dietary_restrictions) if dietary_restrictions else 'None'}
Location: {location}

Provide TWO options:

**Option 1: Healthy Swap (Home Version)**
- Organic, home-cooked version of what they're craving
- Full recipe with ingredients (note Dirty Dozen items that MUST be organic)
- Nutritional breakdown: calories, protein, carbs, fats
- Prep time and difficulty

**Option 2: Premium Indulgence**
- Best local restaurant in {location} that serves this
- Specific dish recommendation
- Price range
- Why this place is special

Format as structured JSON with "healthy_swap" and "premium_indulgence" keys."""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.5, json_mode=True
        )

        try:
            parsed = json.loads(response)
            return {"success": True, "craving": craving, **parsed}
        except json.JSONDecodeError:
            return {
                "success": True,
                "craving": craving,
                "healthy_swap": response[:len(response)//2],
                "premium_indulgence": response[len(response)//2:],
            }

    async def suggest_healthy_swap(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest healthy alternatives for a food item."""
        food = task.get("food", "")
        goal = task.get("goal", "balanced nutrition")

        prompt = f"""Suggest a healthy swap for: "{food}"
Health goal: {goal}

Include:
1. The swap ingredient/meal
2. Why it's healthier
3. Nutritional comparison (original vs swap)
4. Is it on the Dirty Dozen? (must buy organic if yes)
5. Simple recipe if applicable"""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.5
        )

        return {"success": True, "original": food, "recommendation": response}

    async def create_meal_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a weekly meal plan with macro tracking."""
        preferences = task.get("preferences", {})
        budget = task.get("budget", "balanced")
        family_size = task.get("family_size", 4)

        prompt = f"""Create a 7-day meal plan.

Family size: {family_size}
Budget tier: {budget}
Preferences: {json.dumps(preferences, default=str)}

For each day, provide breakfast, lunch, dinner, and snacks.
Include:
- Total daily macros (calories, protein, carbs, fats)
- Grocery list with Dirty Dozen items marked as "MUST BUY ORGANIC"
- Estimated daily cost per person
- Prep time for each meal

Respond in JSON format."""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.6, json_mode=True
        )

        try:
            plan = json.loads(response)
            return {"success": True, "meal_plan": plan}
        except json.JSONDecodeError:
            return {"success": True, "meal_plan": response}

    async def shopping_advice(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Quality-first shopping recommendations."""
        item = task.get("item", "")
        budget = task.get("budget")
        quality_tier = task.get("quality_tier", "balanced")

        dirty_dozen = [
            "strawberries", "spinach", "kale", "peaches", "pears",
            "nectarines", "apples", "grapes", "bell peppers",
            "cherries", "blueberries", "green beans",
        ]
        clean_fifteen = [
            "avocados", "sweet corn", "pineapple", "onions", "papaya",
            "sweet peas", "asparagus", "honeydew", "kiwi", "cabbage",
            "mushrooms", "mangoes", "sweet potatoes", "watermelon", "carrots",
        ]

        item_lower = item.lower()
        is_dirty = any(d in item_lower for d in dirty_dozen)
        is_clean = any(c in item_lower for c in clean_fifteen)

        ewg_note = ""
        if is_dirty:
            ewg_note = f"⚠️ '{item}' is on the DIRTY DOZEN list — ALWAYS buy organic."
        elif is_clean:
            ewg_note = f"✅ '{item}' is on the Clean 15 — conventional is fine."

        prompt = f"""Shopping advice for: "{item}"
Budget: {"$" + str(budget) if budget else "flexible"}
Quality tier: {quality_tier}
EWG Status: {ewg_note or "Not on either list"}

Recommend:
1. Best retailer to buy from (Whole Foods, Thrive Market, Target Organic, etc.)
2. Expected price range
3. Quality indicators to look for
4. Any current deals or seasonal savings
5. Storage tips"""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.5
        )

        return {
            "success": True,
            "item": item,
            "ewg_status": "dirty_dozen" if is_dirty else "clean_fifteen" if is_clean else "unlisted",
            "ewg_note": ewg_note,
            "recommendation": response,
        }

    async def analyze_travel_impact(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze personal financial impact of travel."""
        flight_cost = task.get("flight_cost", 0)
        monthly_income = task.get("monthly_income", 10000)
        trading_profit = task.get("monthly_trading_profit", 2000)
        destination = task.get("destination", "")

        impact_pct = (flight_cost / monthly_income) * 100 if monthly_income > 0 else 0
        trading_impact = (flight_cost / trading_profit) * 100 if trading_profit > 0 else 0

        if impact_pct > 50:
            verdict = "⚠️ High Impact — Consider waiting or finding alternatives"
        elif impact_pct > 25:
            verdict = "🟡 Moderate Impact — Affordable but plan carefully"
        else:
            verdict = "✅ Low Impact — Book with confidence"

        prompt = f"""Analyze the personal impact of this trip:

Destination: {destination}
Flight cost: ${flight_cost:,.2f}
As % of monthly income: {impact_pct:.1f}%
As % of monthly trading profits: {trading_impact:.1f}%
Verdict: {verdict}

Provide:
1. Financial impact assessment
2. Best time to book for savings
3. Alternative destinations at lower cost
4. How many trading days to cover this cost"""

        analysis = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.5
        )

        return {
            "success": True,
            "destination": destination,
            "flight_cost": flight_cost,
            "impact_percent": round(impact_pct, 1),
            "trading_days_to_cover": round(flight_cost / (trading_profit / 22), 1) if trading_profit > 0 else None,
            "verdict": verdict,
            "analysis": analysis,
        }

    async def create_wellness_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a personalized wellness plan."""
        goals = task.get("goals", ["general fitness"])
        current_activity = task.get("current_activity", "sedentary")

        prompt = f"""Create a personalized wellness plan.

Goals: {', '.join(goals)}
Current activity level: {current_activity}

Include:
1. Weekly exercise schedule (specific exercises, duration, intensity)
2. Sleep optimization tips
3. Stress management techniques
4. Hydration goals
5. Progress milestones for 30/60/90 days"""

        response = await self.ollama.generate(
            prompt, system=SYSTEM_PROMPT, temperature=0.6
        )

        return {"success": True, "wellness_plan": response}
