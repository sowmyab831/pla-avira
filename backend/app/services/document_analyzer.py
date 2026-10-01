"""Document analyzer service for assistant integration."""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import httpx
from app.services.file_storage import get_file_storage
from app.routes.finance import transactions_store
from app.routes.health import health_reports_store, lab_results_store

logger = logging.getLogger(__name__)

class DocumentAnalyzer:
    """Analyzes uploaded documents and provides context to the assistant."""
    
    def __init__(self):
        """Initialize document analyzer."""
        self.storage = get_file_storage()
    
    async def get_financial_context(self, user_id: str = "default") -> Dict[str, Any]:
        """Get financial document context for assistant."""
        files = self.storage.list_files(category="finance", user_id=user_id)
        
        # Get transaction data from finance routes
        from app.routes.finance import transactions_store
        transactions = transactions_store if transactions_store else []
        
        if not transactions:
            return {
                "has_data": False,
                "message": "No financial data uploaded yet"
            }
        
        # Calculate summary
        total_spent = sum(t.amount for t in transactions)
        categories = {}
        for t in transactions:
            cat = t.category if hasattr(t, 'category') else 'Other'
            categories[cat] = categories.get(cat, 0) + (t.amount if hasattr(t, 'amount') else 0)
        
        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "has_data": True,
            "files_count": len(files),
            "total_spent": round(total_spent, 2),
            "transaction_count": len(transactions),
            "top_categories": dict(top_categories),
            "files": [{"filename": f["filename"], "upload_time": f["upload_time"]} for f in files[:5]],
            "analysis_ready": True
        }
    
    async def get_health_context(self, user_id: str = "default") -> Dict[str, Any]:
        """Get health document context for assistant."""
        files = self.storage.list_files(category="health", user_id=user_id)
        
        # Get lab results from health routes
        from app.routes.health import health_reports_store

        user_reports = [r for r in health_reports_store if r.get("user_id") == user_id]

        if not user_reports:
            return {
                "has_data": False,
                "message": "No health data uploaded yet"
            }

        latest_report = user_reports[-1]
        
        if not latest_report:
            return {"has_data": False}
        
        alerts = latest_report.get("alerts", [])
        lab_results = latest_report.get("lab_results", [])
        
        return {
            "has_data": True,
            "files_count": len(files),
            "latest_report_date": latest_report.get("uploaded_at"),
            "total_tests": len(lab_results),
            "alerts_count": len(alerts),
            "alerts": alerts[:5],
            "abnormal_results": [r for r in lab_results if r.get("is_abnormal")],
            "files": [{"filename": f["filename"], "upload_time": f["upload_time"]} for f in files[:5]],
            "analysis_ready": True
        }
    
    async def get_school_context(self, user_id: str = "default") -> Dict[str, Any]:
        """Get school calendar context for assistant."""
        files = self.storage.list_files(category="school", user_id=user_id)
        
        return {
            "has_data": len(files) > 0,
            "files_count": len(files),
            "files": [{"filename": f["filename"], "upload_time": f["upload_time"]} for f in files[:5]]
        }
    
    async def analyze_financial_health(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze financial health and provide recommendations."""
        if not context.get("has_data"):
            return {"recommendations": ["Upload financial statements to get personalized advice"]}
        
        total_spent = context.get("total_spent", 0)
        categories = context.get("top_categories", {})
        
        recommendations = []
        insights = []
        
        # Spending analysis
        if total_spent > 0:
            insights.append(f"Total spending: ${total_spent:,.2f}")
            
            # Category-specific advice
            for category, amount in categories.items():
                percentage = (amount / total_spent) * 100
                if percentage > 30:
                    recommendations.append(
                        f"High spending in {category} ({percentage:.1f}%). Consider reviewing these expenses."
                    )
        
        # General recommendations
        recommendations.extend([
            "Set up automatic savings transfers",
            "Review subscription services for unused accounts",
            "Consider high-yield savings accounts for emergency funds",
            "Track spending patterns to identify areas for optimization"
        ])
        
        return {
            "insights": insights,
            "recommendations": recommendations[:5],
            "spending_breakdown": categories
        }
    
    async def compare_with_internet_data(
        self, 
        category: str, 
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare user data with internet benchmarks (simulated)."""
        
        # In production, this would call external APIs for real comparisons
        # For now, providing simulated benchmarks
        
        benchmarks = {
            "finance": {
                "average_monthly_spending": 3500,
                "recommended_savings_rate": 0.20,
                "emergency_fund_months": 6,
                "categories": {
                    "Groceries": {"average": 600, "recommended_max": 800},
                    "Utilities": {"average": 200, "recommended_max": 300},
                    "Entertainment": {"average": 300, "recommended_max": 400},
                    "Transport": {"average": 400, "recommended_max": 600},
                }
            },
            "health": {
                "checkup_frequency_months": 12,
                "recommended_tests": ["CBC", "Lipid Panel", "Glucose", "Vitamin D"],
                "normal_ranges_note": "Reference ranges vary by lab and demographics"
            }
        }
        
        if category == "finance":
            user_spending = user_data.get("total_spent", 0)
            avg_spending = benchmarks["finance"]["average_monthly_spending"]
            
            comparison = {
                "your_spending": user_spending,
                "average_spending": avg_spending,
                "difference": user_spending - avg_spending,
                "status": "above_average" if user_spending > avg_spending else "below_average",
                "recommendations": []
            }
            
            if user_spending > avg_spending:
                comparison["recommendations"].append(
                    f"Your spending is ${user_spending - avg_spending:.2f} above average. "
                    "Consider creating a budget to track expenses."
                )
            
            # Category comparisons
            user_categories = user_data.get("top_categories", {})
            category_comparisons = {}
            
            for cat, user_amount in user_categories.items():
                if cat in benchmarks["finance"]["categories"]:
                    bench = benchmarks["finance"]["categories"][cat]
                    category_comparisons[cat] = {
                        "your_amount": user_amount,
                        "average": bench["average"],
                        "recommended_max": bench["recommended_max"],
                        "status": "high" if user_amount > bench["recommended_max"] else "normal"
                    }
            
            comparison["category_comparisons"] = category_comparisons
            return comparison
        
        elif category == "health":
            return {
                "benchmarks": benchmarks["health"],
                "note": "Consult with healthcare provider for personalized advice"
            }
        
        return {"message": "Comparison not available for this category"}
    
    async def get_savings_opportunities(self, financial_context: Dict[str, Any]) -> List[str]:
        """Identify savings opportunities based on spending patterns."""
        opportunities = []
        
        categories = financial_context.get("top_categories", {})
        total = financial_context.get("total_spent", 0)
        
        if total == 0:
            return ["Upload financial data to identify savings opportunities"]
        
        # High spending categories
        for category, amount in categories.items():
            percentage = (amount / total) * 100
            
            if category == "Entertainment" and percentage > 15:
                opportunities.append(
                    f"Entertainment spending is {percentage:.1f}% of total. "
                    "Consider free alternatives like library services, parks, or streaming service rotation."
                )
            
            if category == "Utilities" and amount > 300:
                opportunities.append(
                    "High utility costs detected. Consider energy-efficient appliances, "
                    "LED bulbs, and programmable thermostats."
                )
            
            if category == "Transport" and amount > 500:
                opportunities.append(
                    "Transportation costs are high. Explore carpooling, public transit, "
                    "or bike-sharing programs."
                )
        
        # Generic opportunities
        opportunities.extend([
            "Review subscriptions: Cancel unused services (avg savings: $20-50/month)",
            "Negotiate bills: Call providers for better rates on internet, phone, insurance",
            "Use cashback apps and credit card rewards (potential: 1-5% back)",
            "Buy generic brands for groceries (potential savings: 20-30%)",
            "Meal prep to reduce dining out costs"
        ])
        
        return opportunities[:7]


# Singleton instance
_document_analyzer: Optional[DocumentAnalyzer] = None

def get_document_analyzer() -> DocumentAnalyzer:
    """Get or create document analyzer instance."""
    global _document_analyzer
    if _document_analyzer is None:
        _document_analyzer = DocumentAnalyzer()
    return _document_analyzer
