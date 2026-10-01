"""
Orchestrator Agent - QWQ:32B for task routing and agentic logic.

The brain of Omni-PLA: classifies user intent, routes to specialist agents,
merges results, and manages multi-step workflows.
"""

from typing import Dict, Any, Optional, List
import logging
import json

from app.agents.base_agent import BaseAgent
from app.integrations.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Orchestrator of Omni-PLA, an elite Personal Life Assistant.

Your role:
1. Classify user intent into categories: stock_analysis, options, news, shopping, travel, nutrition, calendar, health, general
2. Decide which specialist agent(s) to invoke
3. Merge results from multiple agents into a coherent response
4. Handle multi-step workflows (e.g., "buy AAPL if RSI < 30")

Available agents:
- QuantAgent: Options Greeks, risk modeling, portfolio math (DeepSeek-R1)
- LifeAgent: Nutrition, travel, shopping, lifestyle (Llama 3.3 70B)
- PolicyAgent: News analysis, sentiment scoring, geopolitical risk (Mistral 7B)

Always respond in JSON with this schema:
{
  "intent": "category",
  "agents_needed": ["agent1", "agent2"],
  "plan": ["step1", "step2"],
  "priority": "high|medium|low",
  "context": {}
}"""


class OrchestratorAgent(BaseAgent):
    """
    Routes tasks to specialist agents and merges results.
    Uses QWQ:32B for complex reasoning about task decomposition.
    """

    def __init__(self):
        super().__init__(
            name="OrchestratorAgent",
            model="qwq:32b",
            temperature=0.3,
        )
        self.ollama = OllamaClient.for_role("orchestrator")

    async def validate_input(self, task: Dict[str, Any]) -> bool:
        """Any task with a 'query' or 'type' field is valid."""
        return "query" in task or "type" in task

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Classify intent and create execution plan."""
        task_type = task.get("type", "classify")

        if task_type == "classify":
            return await self.classify_intent(task)
        elif task_type == "merge":
            return await self.merge_results(task)
        elif task_type == "plan":
            return await self.create_plan(task)

        return {"success": False, "error": f"Unknown orchestrator task: {task_type}"}

    async def classify_intent(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Classify user query into intent + required agents."""
        query = task.get("query", "")

        prompt = f"""Classify this user request and determine which agents to invoke.

User request: "{query}"

Respond in JSON only."""

        response = await self.ollama.generate(
            prompt,
            system=SYSTEM_PROMPT,
            temperature=0.1,
            json_mode=True,
        )

        try:
            parsed = json.loads(response)
            return {"success": True, "classification": parsed}
        except json.JSONDecodeError:
            # Fallback classification based on keywords
            return {
                "success": True,
                "classification": self._keyword_classify(query),
            }

    def _keyword_classify(self, query: str) -> Dict[str, Any]:
        """Fast keyword-based intent classification as fallback."""
        q = query.lower()

        intent_map = {
            "stock_analysis": ["stock", "price", "ticker", "market", "buy", "sell", "portfolio", "invest"],
            "options": ["option", "call", "put", "spread", "greeks", "delta", "theta", "iv", "strike"],
            "news": ["news", "headline", "market brief", "knowledge pill", "reuters", "influencer"],
            "shopping": ["buy", "shop", "price", "deal", "coupon", "organic", "grocery"],
            "travel": ["flight", "travel", "hotel", "trip", "vacation", "destination"],
            "nutrition": ["meal", "food", "craving", "nutrition", "diet", "recipe", "calorie"],
            "calendar": ["calendar", "event", "schedule", "reminder", "appointment"],
            "health": ["health", "lab", "blood", "doctor", "wellness", "exercise"],
        }

        for intent, keywords in intent_map.items():
            if any(kw in q for kw in keywords):
                agents = {
                    "stock_analysis": ["quant"],
                    "options": ["quant"],
                    "news": ["policy"],
                    "shopping": ["life"],
                    "travel": ["life"],
                    "nutrition": ["life"],
                    "calendar": ["life"],
                    "health": ["life"],
                }.get(intent, ["life"])

                return {
                    "intent": intent,
                    "agents_needed": agents,
                    "plan": [f"Route to {', '.join(agents)} agent(s)"],
                    "priority": "high" if intent in ("stock_analysis", "options") else "medium",
                    "context": {"original_query": query},
                }

        return {
            "intent": "general",
            "agents_needed": ["life"],
            "plan": ["Handle as general assistant query"],
            "priority": "medium",
            "context": {"original_query": query},
        }

    async def merge_results(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Merge results from multiple agents into a unified response."""
        results = task.get("results", [])
        original_query = task.get("query", "")

        if not results:
            return {"success": False, "error": "No results to merge"}

        if len(results) == 1:
            return {"success": True, "merged": results[0]}

        prompt = f"""Merge these agent results into a single coherent response for the user.

Original query: "{original_query}"

Agent results:
{json.dumps(results, indent=2, default=str)[:3000]}

Create a unified, well-structured response that combines insights from all agents.
Be concise but comprehensive."""

        merged = await self.ollama.generate(prompt, temperature=0.3)

        return {
            "success": True,
            "merged": merged,
            "sources": [r.get("agent", "unknown") for r in results],
        }

    async def create_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a multi-step execution plan for complex queries."""
        query = task.get("query", "")

        prompt = f"""Create a step-by-step execution plan for this complex request.

Request: "{query}"

For each step, specify:
1. Which agent handles it
2. What data it needs
3. Dependencies on other steps

Respond in JSON with a "steps" array."""

        response = await self.ollama.generate(
            prompt,
            system=SYSTEM_PROMPT,
            temperature=0.2,
            json_mode=True,
        )

        try:
            plan = json.loads(response)
            return {"success": True, "plan": plan}
        except json.JSONDecodeError:
            return {
                "success": True,
                "plan": {
                    "steps": [
                        {"step": 1, "agent": "orchestrator", "action": "classify", "data": query}
                    ]
                },
            }
