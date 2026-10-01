"""
Domain prompt builders used by legacy analysis routes.

All system-level rules now come from `app.ai.prompts` (single source of truth
for the investing / finance / health / shopping skills). These builders only
assemble the *grounded context block* — the data the model is allowed to
reason about — and append the task question.
"""
from typing import Any, Dict, List, Optional

from app.ai.prompts import FINANCE, HEALTH, INVESTING, GENERAL


def _ctx(title: str, rows: Dict[str, Any]) -> str:
    body = "\n".join(f"- {k}: {v}" for k, v in rows.items() if v not in (None, "", [], {}))
    return f"{title}\n{body}\n" if body else f"{title}\n- (no data supplied)\n"


class EnhancedPrompts:
    """Context-aware prompts. Numbers come only from the supplied dicts."""

    @staticmethod
    def investment_analysis_prompt(symbol: str, quote_data: Dict, news: List[Dict],
                                   user_context: Optional[Dict] = None) -> str:
        source = quote_data.get("source", "market data feed")
        asof = quote_data.get("as_of") or quote_data.get("timestamp") or "time not supplied"
        ccy = "INR" if symbol.upper().endswith((".NS", ".BO")) else "USD"
        prompt = INVESTING + "\n\n" + _ctx(f"QUOTE for {symbol} ({source}, {asof}, {ccy})", {
            "price": quote_data.get("price"), "change_percent": quote_data.get("change_percent"),
            "volume": quote_data.get("volume"), "rsi_14": quote_data.get("rsi"), "sma_50": quote_data.get("sma_50"),
            "sma_200": quote_data.get("sma_200"), "pe_ratio": quote_data.get("pe_ratio"),
            "support": quote_data.get("support"), "resistance": quote_data.get("resistance"),
        })
        if news:
            prompt += "RECENT HEADLINES (titles only; do not infer facts beyond them)\n" + "\n".join(
                f"- {a.get('title', 'N/A')} ({a.get('source', 'source?')}, {a.get('published_at', 'date?')})" for a in news[:5]) + "\n"
        if user_context:
            prompt += _ctx("INVESTOR PROFILE (user-stated)", {
                "risk_tolerance": user_context.get("risk_tolerance"), "horizon": user_context.get("horizon"),
                "goals": ", ".join(user_context.get("goals", []) or []),
            })
        prompt += ("\nTASK: In under 250 words: (1) what the data shows — trend, momentum, valuation context; "
                   "(2) bull case and bear case from the evidence above only; (3) the 2–3 things to verify before acting; "
                   "(4) which fields above were missing. Do not give a buy/sell instruction or a price target.")
        return prompt

    @staticmethod
    def finance_analysis_prompt(income: float, expenses: float, savings: float, debt: float, goals: List[str],
                                currency: str = "USD", country: str = "US") -> str:
        surplus = income - expenses
        rate = (surplus / income * 100) if income > 0 else 0.0
        prompt = FINANCE + "\n\n" + _ctx(f"HOUSEHOLD SNAPSHOT (user-entered, monthly, {currency}, {country})", {
            "income": f"{income:,.2f}", "expenses": f"{expenses:,.2f}", "surplus (income − expenses)": f"{surplus:,.2f}",
            "savings_rate": f"{rate:.1f}%", "current_savings": f"{savings:,.2f}", "total_debt": f"{debt:,.2f}",
            "goals": "; ".join(goals) if goals else None,
        })
        prompt += ("\nTASK: In under 300 words: emergency-fund coverage in months (show the division), the single largest "
                   "lever in this budget, a debt-payoff order with reasoning, and 3 next steps the user can do this week. "
                   "Use only the figures above; label anything you assume.")
        return prompt

    @staticmethod
    def health_analysis_prompt(symptoms: List[str], medical_history: List[str], age: int, lifestyle: Dict,
                               lab_results: Optional[List[Dict]] = None) -> str:
        """Preparation and tracking only. Never asks the model for causes or conditions."""
        prompt = HEALTH + "\n\n" + _ctx("USER-REPORTED CONTEXT", {
            "age": age, "reported_symptoms": ", ".join(symptoms) if symptoms else None,
            "history (user-stated)": ", ".join(medical_history) if medical_history else None,
            "exercise": lifestyle.get("exercise"), "diet": lifestyle.get("diet"), "sleep_hours": lifestyle.get("sleep"),
        })
        if lab_results:
            prompt += "LAB VALUES (from the user's report; reference ranges as printed)\n" + "\n".join(
                f"- {r.get('test_name')}: {r.get('value')} {r.get('unit', '')} (ref {r.get('reference_range', 'not printed')})"
                for r in lab_results[:25]) + "\n"
        prompt += ("\nTASK: (1) If any reported symptom is a red flag, output ONLY the urgent-care message. Otherwise: "
                   "(2) list values outside their printed reference range, stating only that they are outside range; "
                   "(3) draft 5 questions the user can bring to their doctor; (4) suggest 2–3 metrics worth logging in the app. "
                   "Do not name conditions, causes, or dosages.")
        return prompt

    @staticmethod
    def planning_assistant_prompt(task_type: str, context: Dict, constraints: List[str]) -> str:
        prompt = GENERAL + "\n\n" + _ctx(f"PLANNING CONTEXT for {task_type}", context)
        if constraints:
            prompt += "CONSTRAINTS\n" + "\n".join(f"- {c}" for c in constraints) + "\n"
        prompt += "\nTASK: A dated checklist with owners, the critical path, and 2 risks with mitigations. Under 250 words."
        return prompt

    @staticmethod
    def investment_chat_prompt(user_message: str, portfolio_context: Optional[Dict] = None,
                               conversation_history: Optional[List[Dict]] = None) -> str:
        prompt = INVESTING + "\n\n"
        if portfolio_context:
            holdings = portfolio_context.get("holdings", []) or []
            total = portfolio_context.get("total_value", 0) or 0
            gl = portfolio_context.get("gain_loss", 0) or 0
            prompt += _ctx(f"PORTFOLIO (app data, {portfolio_context.get('as_of', 'time not supplied')})", {
                "total_value": f"{total:,.2f} {portfolio_context.get('currency', 'USD')}",
                "gain_loss": f"{gl:,.2f} ({(gl / total * 100) if total else 0:.2f}%)", "holdings_count": len(holdings),
            })
            for h in holdings[:8]:
                prompt += f"- {h.get('symbol')}: {h.get('shares')} sh @ {h.get('current_price')} (avg cost {h.get('average_cost', '?')})\n"
        if conversation_history:
            prompt += "\nRECENT CONVERSATION\n" + "\n".join(
                f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in conversation_history[-5:]) + "\n"
        prompt += f"\nQUESTION: {user_message}\n\nAnswer in under 200 words using only the portfolio data and conversation above."
        return prompt


enhanced_prompts = EnhancedPrompts()
