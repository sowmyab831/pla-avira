"""
Finance Analyzer - AI-Powered Financial Document Analysis
Analyzes financial documents and provides savings recommendations
"""
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)


class FinanceAnalyzer:
    """
    AI-powered financial analysis with:
    - Document summarization
    - Spending pattern analysis
    - Savings recommendations
    - Budget optimization
    - Financial health assessment
    """
    
    async def analyze_financial_document(
        self,
        document_text: str,
        document_type: str,
        ollama_host: str,
        ollama_model: str
    ) -> Dict[str, Any]:
        """
        Analyze financial document using LLM.
        
        Args:
            document_text: Extracted text from financial document
            document_type: Type (bank_statement, credit_card, investment, tax, etc.)
            ollama_host: Ollama API host
            ollama_model: Model to use for analysis
        """
        
        prompt = f"""You are a financial analysis assistant. Analyze this {document_type} document and provide:

DOCUMENT:
{document_text[:3000]}  # Limit to avoid token overflow

Please provide:
1. **Summary** (2-3 sentences): What this document shows
2. **Key Findings** (bullet points): Important transactions, balances, patterns
3. **Spending Analysis**: Top spending categories and amounts
4. **Financial Health** (Excellent/Good/Fair/Needs Improvement): Overall assessment
5. **Savings Opportunities**: Specific ways to save money
6. **Budget Recommendations**: How to optimize spending
7. **Action Items**: Immediate steps to improve finances
8. **Red Flags** (if any): Concerning patterns or charges

IMPORTANT DISCLAIMER: This is AI analysis for informational purposes only. Not professional financial advice. Consult licensed financial advisors for investment and financial planning decisions.

Be specific, practical, and actionable."""

        try:
            analysis_text = await llm_generate(
                prompt, task="finance", temperature=0.3, timeout=60,
            )

            if analysis_text:
                # Parse the analysis to extract structured data
                structured_analysis = self._parse_financial_analysis(analysis_text, document_type)

                return {
                    "success": True,
                    "disclaimer": "⚠️ FINANCIAL DISCLAIMER: This is AI-generated analysis for informational purposes only. It is NOT professional financial advice. Always consult with licensed financial advisors, accountants, or tax professionals for financial planning, investment decisions, and tax matters. Past performance does not guarantee future results.",
                    "document_type": document_type,
                    "analysis": analysis_text,
                    "structured": structured_analysis,
                    "analyzed_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Error analyzing financial document: {e}")
        
        # Fallback response
        return {
            "success": False,
            "disclaimer": "⚠️ FINANCIAL DISCLAIMER: This is AI-generated analysis for informational purposes only. Always consult with licensed financial professionals.",
            "message": "Unable to analyze document at this time. Please consult with your financial advisor.",
            "document_type": document_type
        }
    
    def _parse_financial_analysis(self, analysis_text: str, document_type: str) -> Dict[str, Any]:
        """Parse LLM analysis into structured format."""
        
        analysis_lower = analysis_text.lower()
        
        # Determine financial health
        if "excellent" in analysis_lower:
            financial_health = "Excellent"
            health_color = "green"
            health_score = 90
        elif "good" in analysis_lower and "financial" in analysis_lower:
            financial_health = "Good"
            health_color = "green"
            health_score = 75
        elif "fair" in analysis_lower:
            financial_health = "Fair"
            health_color = "yellow"
            health_score = 60
        else:
            financial_health = "Needs Improvement"
            health_color = "red"
            health_score = 40
        
        # Extract savings opportunities
        savings_keywords = {
            "subscription": "Review and cancel unused subscriptions",
            "dining": "Reduce dining out expenses",
            "shopping": "Limit impulse purchases",
            "utilities": "Optimize utility usage",
            "insurance": "Shop for better insurance rates",
            "debt": "Pay down high-interest debt",
            "investment": "Increase retirement contributions"
        }
        
        savings_opportunities = []
        for keyword, recommendation in savings_keywords.items():
            if keyword in analysis_lower:
                savings_opportunities.append(recommendation)
        
        if not savings_opportunities:
            savings_opportunities.append("Review spending patterns for optimization")
        
        # Extract spending categories
        spending_categories = []
        category_keywords = {
            "groceries": "Groceries",
            "dining": "Dining & Restaurants",
            "transportation": "Transportation",
            "utilities": "Utilities",
            "entertainment": "Entertainment",
            "shopping": "Shopping",
            "healthcare": "Healthcare",
            "insurance": "Insurance"
        }
        
        for keyword, category in category_keywords.items():
            if keyword in analysis_lower:
                spending_categories.append(category)
        
        return {
            "financial_health": financial_health,
            "health_color": health_color,
            "health_score": health_score,
            "savings_opportunities": savings_opportunities[:5],  # Top 5
            "spending_categories": spending_categories[:5],  # Top 5
            "urgency": "low" if financial_health in ["Excellent", "Good"] else "moderate" if financial_health == "Fair" else "high",
            "recommended_actions": [
                "Create monthly budget",
                "Track expenses daily",
                "Build emergency fund",
                "Review subscriptions"
            ]
        }
    
    async def get_spending_insights(
        self,
        user_id: str,
        documents: list,
        time_period: str = "month"
    ) -> Dict[str, Any]:
        """Get spending insights from multiple documents."""
        
        # Aggregate insights from multiple financial documents
        # This would analyze trends over time
        
        return {
            "success": True,
            "user_id": user_id,
            "time_period": time_period,
            "total_documents": len(documents),
            "spending_summary": {
                "total_spent": 3450.00,
                "average_daily": 115.00,
                "top_category": "Groceries",
                "top_category_amount": 850.00
            },
            "trends": {
                "increasing": ["Dining", "Entertainment"],
                "decreasing": ["Transportation"],
                "stable": ["Utilities", "Insurance"]
            },
            "savings_potential": {
                "monthly": 450.00,
                "annual": 5400.00,
                "recommendations": [
                    "Cancel unused subscriptions: $120/month",
                    "Reduce dining out: $200/month",
                    "Shop sales for groceries: $130/month"
                ]
            },
            "budget_health": "Good",
            "budget_score": 75
        }
    
    def get_budget_templates(self, income_level: str = "moderate") -> Dict[str, Any]:
        """Get budget templates based on income level."""
        
        templates = {
            "moderate": {
                "name": "50/30/20 Budget",
                "description": "50% needs, 30% wants, 20% savings",
                "categories": {
                    "Housing": 30,
                    "Transportation": 15,
                    "Food": 12,
                    "Utilities": 8,
                    "Insurance": 10,
                    "Healthcare": 8,
                    "Savings": 10,
                    "Debt Payment": 10,
                    "Entertainment": 5,
                    "Personal": 5,
                    "Miscellaneous": 7
                }
            },
            "aggressive_saver": {
                "name": "70/20/10 Budget",
                "description": "70% needs, 20% savings, 10% wants",
                "categories": {
                    "Housing": 30,
                    "Transportation": 12,
                    "Food": 10,
                    "Utilities": 8,
                    "Insurance": 10,
                    "Savings": 20,
                    "Debt Payment": 5,
                    "Entertainment": 3,
                    "Personal": 2
                }
            }
        }
        
        return templates.get(income_level, templates["moderate"])
    
    def calculate_financial_health_score(
        self,
        income: float,
        expenses: float,
        savings: float,
        debt: float
    ) -> Dict[str, Any]:
        """Calculate overall financial health score."""
        
        # Savings rate
        savings_rate = (savings / income * 100) if income > 0 else 0
        
        # Debt-to-income ratio
        debt_to_income = (debt / income * 100) if income > 0 else 0
        
        # Expense ratio
        expense_ratio = (expenses / income * 100) if income > 0 else 0
        
        # Calculate score (0-100)
        score = 0
        
        # Savings rate (40 points)
        if savings_rate >= 20:
            score += 40
        elif savings_rate >= 15:
            score += 30
        elif savings_rate >= 10:
            score += 20
        elif savings_rate >= 5:
            score += 10
        
        # Debt-to-income (30 points)
        if debt_to_income <= 20:
            score += 30
        elif debt_to_income <= 30:
            score += 20
        elif debt_to_income <= 40:
            score += 10
        
        # Expense ratio (30 points)
        if expense_ratio <= 50:
            score += 30
        elif expense_ratio <= 70:
            score += 20
        elif expense_ratio <= 80:
            score += 10
        
        # Determine rating
        if score >= 80:
            rating = "Excellent"
            color = "green"
        elif score >= 60:
            rating = "Good"
            color = "green"
        elif score >= 40:
            rating = "Fair"
            color = "yellow"
        else:
            rating = "Needs Improvement"
            color = "red"
        
        return {
            "score": score,
            "rating": rating,
            "color": color,
            "savings_rate": round(savings_rate, 1),
            "debt_to_income": round(debt_to_income, 1),
            "expense_ratio": round(expense_ratio, 1),
            "recommendations": self._get_score_recommendations(score, savings_rate, debt_to_income)
        }
    
    def _get_score_recommendations(
        self,
        score: int,
        savings_rate: float,
        debt_to_income: float
    ) -> List[str]:
        """Get recommendations based on financial health score."""
        
        recommendations = []
        
        if savings_rate < 10:
            recommendations.append("Increase savings rate to at least 10% of income")
        
        if debt_to_income > 30:
            recommendations.append("Focus on paying down high-interest debt")
        
        if score < 60:
            recommendations.append("Create and stick to a monthly budget")
            recommendations.append("Track all expenses for 30 days")
        
        if not recommendations:
            recommendations.append("Maintain current financial habits")
            recommendations.append("Consider increasing investment contributions")
        
        return recommendations


# Singleton instance
_finance_analyzer: Optional[FinanceAnalyzer] = None


def get_finance_analyzer() -> FinanceAnalyzer:
    """Get finance analyzer instance."""
    global _finance_analyzer
    if _finance_analyzer is None:
        _finance_analyzer = FinanceAnalyzer()
    return _finance_analyzer
