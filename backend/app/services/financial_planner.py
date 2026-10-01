"""
Financial Planner Service
─────────────────────────
Deterministic projections and actionable financial planning:
  • Emergency fund calculator & gap analysis
  • Debt payoff projection (avalanche + snowball) with total interest
  • Retirement savings with compound growth to target age
  • Savings goal timeline with monthly contribution
  • Net worth trajectory over time
  • 50/30/20 budget breakdown from real income
  • Goal tracking with progress % and milestones
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path("/data/documents") if Path("/data/documents").exists() else Path("./data")
_GOALS_FILE = _DATA_DIR / "financial_goals.json"


def _load_goals() -> List[Dict[str, Any]]:
    if _GOALS_FILE.exists():
        try:
            return json.loads(_GOALS_FILE.read_text())
        except Exception:
            pass
    return []


def _save_goals(goals: List[Dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _GOALS_FILE.write_text(json.dumps(goals, indent=2))


# ── Calculators ──────────────────────────────────────────────────────────────

def emergency_fund_needed(monthly_expenses: float, months: int = 6) -> Dict[str, Any]:
    """How much emergency fund is needed and where the user stands."""
    target = monthly_expenses * months
    return {
        "target": round(target, 2),
        "months_covered": months,
        "per_month_salary_band": round(target / months, 2),
    }


def debt_payoff(debts: List[Dict[str, Any]], extra_monthly: float = 0, method: str = "avalanche") -> Dict[str, Any]:
    """
    Project full debt payoff timeline.
    debts: [{name, balance, rate, min_payment}]
    method: avalanche (highest rate first) or snowball (lowest balance first).
    """
    if not debts:
        return {"months": 0, "total_interest": 0, "schedule": []}

    remaining = [
        {"name": d["name"], "balance": float(d["balance"]), "rate": float(d["rate"]) / 100,
         "min_payment": float(d["min_payment"]), "original_balance": float(d["balance"])}
        for d in debts
    ]

    if method == "avalanche":
        remaining.sort(key=lambda x: -x["rate"])
    else:
        remaining.sort(key=lambda x: x["balance"])

    month = 0
    max_months = 600
    total_interest = 0.0
    schedule: List[Dict[str, Any]] = []

    while remaining and month < max_months:
        month += 1
        month_data = {"month": month, "payments": [], "extra_applied": extra_monthly > 0}
        active = [d for d in remaining if d["balance"] > 0.01]
        total_min = sum(d["min_payment"] for d in active)
        available_extra = extra_monthly

        for d in active:
            interest = d["balance"] * (d["rate"] / 12)
            total_interest += interest
            d["balance"] += interest
            payment = min(d["min_payment"], d["balance"])
            d["balance"] -= payment
            month_data["payments"].append({
                "name": d["name"], "payment": round(payment, 2),
                "interest": round(interest, 2), "remaining": round(max(0, d["balance"]), 2)
            })

        # Apply extra to the priority debt
        if available_extra > 0 and active:
            priority = active[0]
            apply = min(available_extra, priority["balance"])
            priority["balance"] -= apply
            month_data["payments"][0]["extra"] = round(apply, 2)

        remaining = [d for d in remaining if d["balance"] > 0.01]
        schedule.append(month_data)

    return {
        "method": method,
        "months": month,
        "years": round(month / 12, 1),
        "total_interest": round(total_interest, 2),
        "total_paid": round(sum(d["original_balance"] for d in debts) + total_interest, 2),
        "schedule": schedule,
    }


def retirement_projection(
    current_age: int,
    retirement_age: int,
    current_savings: float,
    monthly_contribution: float,
    annual_return: float = 0.07,
    annual_inflation: float = 0.03,
) -> Dict[str, Any]:
    """Compound-growth retirement projection."""
    years = retirement_age - current_age
    if years <= 0:
        return {"error": "Retirement age must be greater than current age"}

    real_return = (1 + annual_return) / (1 + annual_inflation) - 1
    balance = current_savings
    yearly: List[Dict[str, Any]] = []

    for y in range(1, years + 1):
        balance = balance * (1 + annual_return) + monthly_contribution * 12
        real_balance = balance / ((1 + annual_inflation) ** y)
        yearly.append({
            "age": current_age + y,
            "nominal": round(balance, 2),
            "real_value": round(real_balance, 2),
        })

    final = yearly[-1]
    total_contributed = current_savings + monthly_contribution * 12 * years
    return {
        "current_age": current_age,
        "retirement_age": retirement_age,
        "years": years,
        "monthly_contribution": monthly_contribution,
        "annual_return_pct": round(annual_return * 100, 1),
        "inflation_pct": round(annual_inflation * 100, 1),
        "final_nominal": final["nominal"],
        "final_real": final["real_value"],
        "total_contributed": round(total_contributed, 2),
        "growth_from_returns": round(final["nominal"] - total_contributed, 2),
        "yearly": yearly,
    }


def savings_goal_timeline(
    goal_amount: float,
    current_saved: float,
    monthly_contribution: float,
    annual_return: float = 0.05,
) -> Dict[str, Any]:
    """How many months to reach a savings goal with optional growth."""
    if monthly_contribution <= 0:
        return {"reachable": False, "error": "Monthly contribution must be > 0"}

    balance = current_saved
    month = 0
    monthly_rate = annual_return / 12
    history = []
    while balance < goal_amount and month < 600:
        month += 1
        balance = balance * (1 + monthly_rate) + monthly_contribution
        history.append({"month": month, "balance": round(balance, 2)})

    return {
        "goal": goal_amount,
        "current": current_saved,
        "monthly_contribution": monthly_contribution,
        "months": month,
        "years": round(month / 12, 1),
        "final_balance": round(balance, 2),
        "history": history,
    }


def net_worth_trajectory(
    assets: List[Dict[str, Any]],
    liabilities: List[Dict[str, Any]],
    years_ahead: int = 10,
    annual_growth: float = 0.06,
    annual_debt_paydown: float = 0.03,
) -> List[Dict[str, Any]]:
    """Project net worth year by year."""
    total_assets = sum(a.get("value", 0) for a in assets)
    total_liabilities = sum(l.get("balance", 0) for l in liabilities)
    trajectory = [{
        "year": 0,
        "assets": round(total_assets, 2),
        "liabilities": round(total_liabilities, 2),
        "net_worth": round(total_assets - total_liabilities, 2),
    }]

    for y in range(1, years_ahead + 1):
        total_assets *= (1 + annual_growth)
        total_liabilities *= max(0, 1 - annual_debt_paydown)
        trajectory.append({
            "year": y,
            "assets": round(total_assets, 2),
            "liabilities": round(total_liabilities, 2),
            "net_worth": round(total_assets - total_liabilities, 2),
        })
    return trajectory


def budget_503020(income: float) -> Dict[str, Any]:
    """50/30/20 budget breakdown."""
    needs = income * 0.50
    wants = income * 0.30
    savings = income * 0.20
    return {
        "income": income,
        "needs": round(needs, 2),
        "wants": round(wants, 2),
        "savings": round(savings, 2),
        "breakdown": {
            "needs_pct": 50, "wants_pct": 30, "savings_pct": 20,
            "needs_monthly": round(needs / 12, 2),
            "wants_monthly": round(wants / 12, 2),
            "savings_monthly": round(savings / 12, 2),
        }
    }


# ── Goals ────────────────────────────────────────────────────────────────────

def add_goal(name: str, target: float, deadline: str, monthly_allocation: float) -> Dict[str, Any]:
    goals = _load_goals()
    goal = {
        "id": f"G-{len(goals)+1:03d}",
        "name": name,
        "target": target,
        "saved": 0.0,
        "deadline": deadline,
        "monthly_allocation": monthly_allocation,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    goals.append(goal)
    _save_goals(goals)
    return goal


def update_goal_progress(goal_id: str, amount_saved: float) -> Optional[Dict[str, Any]]:
    goals = _load_goals()
    for g in goals:
        if g["id"] == goal_id:
            g["saved"] = float(amount_saved)
            g["progress_pct"] = round(min(100, (g["saved"] / g["target"]) * 100), 1)
            _save_goals(goals)
            return g
    return None


def list_goals() -> List[Dict[str, Any]]:
    goals = _load_goals()
    for g in goals:
        g["progress_pct"] = round(min(100, (g.get("saved", 0) / g["target"]) * 100), 1) if g["target"] > 0 else 0
    return goals


def delete_goal(goal_id: str) -> bool:
    goals = _load_goals()
    before = len(goals)
    goals = [g for g in goals if g["id"] != goal_id]
    if len(goals) < before:
        _save_goals(goals)
        return True
    return False


# ── LLM Narrative (optional enrichment) ──────────────────────────────────────

async def generate_plan_narrative(context: Dict[str, Any]) -> str:
    """Generate a human-friendly financial plan narrative via local LLM."""
    try:
        from app.services.llm_client import generate as llm_generate
        prompt = (
            "You are a certified financial planner. Write a concise, warm, and actionable "
            "financial plan summary in 3-5 short paragraphs. Use the user's real numbers. "
            "Be specific. Mention their gaps (emergency fund, debt, retirement shortfall) "
            "and give 3 concrete next steps. No disclaimers needed.\n\n"
            f"Context: {json.dumps(context, indent=2)}"
        )
        return await llm_generate(prompt, task="finance", temperature=0.4, timeout=60)
    except Exception:
        pass
    return ""
