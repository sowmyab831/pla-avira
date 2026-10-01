"""
Unified Data Context Service - MCP-style unified access to all app data.

This service provides a single interface for the LLM/Chat to access:
- Calendar events and appointments
- Finance transactions and spending analytics
- Health lab results and reports
- Bills and receipts

All data is accessible through natural language queries.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class DataContextService:
    """Unified data context for LLM access to all app data."""
    
    def __init__(self):
        self._calendar_events: List[Dict] = []
        self._transactions: List[Dict] = []
        self._health_reports: List[Dict] = []
        self._lab_results: List[Dict] = []
        self._bills: List[Dict] = []
        self._user_preferences: Dict = {}
    
    # ============ Calendar Methods ============
    
    def set_calendar_events(self, events: List[Dict]):
        """Update calendar events from calendar module."""
        self._calendar_events = events
    
    def get_calendar_events(self, days: int = 30) -> List[Dict]:
        """Get upcoming calendar events."""
        today = datetime.now().date()
        end_date = today + timedelta(days=days)
        
        upcoming = []
        for event in self._calendar_events:
            try:
                event_date = datetime.strptime(event.get('date', ''), '%Y-%m-%d').date()
                if today <= event_date <= end_date:
                    upcoming.append(event)
            except:
                continue
        
        return sorted(upcoming, key=lambda x: x.get('date', ''))
    
    def find_free_days(self, days: int = 60) -> List[str]:
        """Find days with no events (good for vacation planning)."""
        today = datetime.now().date()
        busy_dates = set()
        
        for event in self._calendar_events:
            try:
                event_date = datetime.strptime(event.get('date', ''), '%Y-%m-%d').date()
                busy_dates.add(event_date)
            except:
                continue
        
        free_days = []
        for i in range(days):
            check_date = today + timedelta(days=i)
            # Include weekends and non-busy days
            if check_date not in busy_dates:
                day_name = check_date.strftime('%A')
                free_days.append({
                    'date': check_date.strftime('%Y-%m-%d'),
                    'day': day_name,
                    'is_weekend': day_name in ['Saturday', 'Sunday']
                })
        
        return free_days
    
    # ============ Finance Methods ============
    
    def set_transactions(self, transactions: List):
        """Update transactions from finance module. Handles both dict and object formats."""
        self._transactions = []
        for t in transactions:
            if isinstance(t, dict):
                self._transactions.append(t)
            else:
                # Convert Pydantic model or object to dict
                try:
                    self._transactions.append(t.dict() if hasattr(t, 'dict') else vars(t))
                except:
                    self._transactions.append({
                        'date': getattr(t, 'date', ''),
                        'description': getattr(t, 'description', ''),
                        'amount': getattr(t, 'amount', 0),
                        'category': getattr(t, 'category', 'Other'),
                    })
    
    def get_spending_summary(self, days: int = 30) -> Dict:
        """Get spending summary for the last N days."""
        total_spent = 0
        by_category = defaultdict(float)
        by_merchant = defaultdict(float)
        transactions_in_period = []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for t in self._transactions:
            # Parse transaction date
            try:
                t_date = datetime.strptime(t.get('date', ''), '%m/%d/%Y')
            except:
                try:
                    t_date = datetime.strptime(t.get('date', ''), '%Y-%m-%d')
                except:
                    t_date = datetime.now()
            
            amount = t.get('amount', 0)
            if amount > 0:  # Only count debits
                if t_date >= cutoff_date:
                    total_spent += amount
                    category = t.get('category', 'Other')
                    by_category[category] += amount
                    merchant = t.get('description', 'Unknown')[:30]
                    by_merchant[merchant] += amount
                    transactions_in_period.append(t)
        
        # Find top spending items
        top_merchants = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:5]
        top_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_spent': total_spent,
            'transaction_count': len(transactions_in_period),
            'top_merchants': top_merchants,
            'top_categories': top_categories,
            'by_category': dict(by_category),
            'period_days': days,
        }
    
    def get_month_over_month(self) -> Dict:
        """Compare spending month over month."""
        now = datetime.now()
        this_month_start = now.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        
        this_month_total = 0
        last_month_total = 0
        
        for t in self._transactions:
            try:
                t_date = datetime.strptime(t.get('date', ''), '%m/%d/%Y')
            except:
                try:
                    t_date = datetime.strptime(t.get('date', ''), '%Y-%m-%d')
                except:
                    continue
            
            amount = t.get('amount', 0)
            if amount > 0:
                if t_date >= this_month_start:
                    this_month_total += amount
                elif t_date >= last_month_start:
                    last_month_total += amount
        
        change = this_month_total - last_month_total
        change_pct = (change / last_month_total * 100) if last_month_total > 0 else 0
        
        return {
            'this_month': this_month_total,
            'last_month': last_month_total,
            'change': change,
            'change_percent': change_pct,
        }
    
    def get_spending_suggestions(self) -> List[str]:
        """Get AI-powered spending suggestions based on patterns."""
        summary = self.get_spending_summary(30)
        suggestions = []
        
        # Analyze top categories
        for category, amount in summary['top_categories']:
            if category == 'Dining' and amount > 500:
                suggestions.append(f"🍽️ Dining out: ${amount:.2f}/month. Consider meal prepping to save ~30%.")
            elif category == 'Shopping' and amount > 300:
                suggestions.append(f"🛍️ Shopping: ${amount:.2f}/month. Try a 24-hour rule before purchases.")
            elif category == 'Entertainment' and amount > 200:
                suggestions.append(f"🎬 Entertainment: ${amount:.2f}/month. Look for free local events.")
            elif category == 'Transport' and amount > 400:
                suggestions.append(f"🚗 Transport: ${amount:.2f}/month. Consider carpooling or public transit.")
        
        # Check for large transactions
        large_txns = [t for t in self._transactions if t.get('amount', 0) > 500]
        if len(large_txns) > 3:
            suggestions.append(f"⚠️ {len(large_txns)} large transactions (>$500). Review for necessity.")
        
        # Month over month
        mom = self.get_month_over_month()
        if mom['change_percent'] > 20:
            suggestions.append(f"📈 Spending up {mom['change_percent']:.1f}% vs last month. Review recent purchases.")
        
        if not suggestions:
            suggestions.append("✅ Your spending looks healthy! Keep up the good habits.")
        
        return suggestions
    
    # ============ Health Methods ============
    
    def set_health_data(self, reports: List[Dict], lab_results: List[Dict]):
        """Update health data from health module."""
        self._health_reports = reports
        self._lab_results = lab_results
    
    def get_health_summary(self) -> Dict:
        """Get health summary with alerts."""
        if not self._lab_results:
            return {'status': 'no_data', 'message': 'No lab results uploaded yet.'}
        
        abnormal = [r for r in self._lab_results if r.get('is_abnormal')]
        
        return {
            'total_tests': len(self._lab_results),
            'abnormal_count': len(abnormal),
            'abnormal_tests': abnormal,
            'last_report_date': self._health_reports[-1].get('uploaded_at') if self._health_reports else None,
        }
    
    def compare_lab_results(self, test_name: str) -> Dict:
        """Compare a specific test across multiple reports."""
        test_name_lower = test_name.lower()
        results = []
        
        for result in self._lab_results:
            if test_name_lower in result.get('test_name', '').lower():
                results.append({
                    'date': result.get('date'),
                    'value': result.get('value'),
                    'unit': result.get('unit'),
                    'is_abnormal': result.get('is_abnormal'),
                    'reference_range': result.get('reference_range'),
                })
        
        if not results:
            return {'found': False, 'message': f'No results found for {test_name}'}
        
        # Sort by date
        results.sort(key=lambda x: x.get('date', ''))
        
        # Calculate trend
        if len(results) >= 2:
            first = results[0]['value']
            last = results[-1]['value']
            trend = 'increasing' if last > first else 'decreasing' if last < first else 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'found': True,
            'test_name': test_name,
            'results': results,
            'trend': trend,
            'latest': results[-1] if results else None,
        }
    
    # ============ Bills Methods ============
    
    def add_bill(self, bill: Dict):
        """Add a parsed bill."""
        self._bills.append(bill)
    
    def get_bills_summary(self) -> Dict:
        """Get summary of all bills."""
        total = sum(b.get('total', 0) for b in self._bills)
        by_vendor = defaultdict(float)
        
        for b in self._bills:
            by_vendor[b.get('vendor', 'Unknown')] += b.get('total', 0)
        
        return {
            'total_bills': len(self._bills),
            'total_amount': total,
            'by_vendor': dict(by_vendor),
        }
    
    # ============ Unified Query Interface ============
    
    def query(self, intent: str, params: Dict = None) -> Dict:
        """
        Unified query interface for LLM.
        
        Intents:
        - spending_summary: Get spending overview
        - top_spending: Get top spending items
        - health_summary: Get health overview
        - compare_test: Compare lab test over time
        - vacation_days: Find free days for vacation
        - upcoming_events: Get upcoming calendar events
        - suggestions: Get spending suggestions
        """
        params = params or {}
        
        if intent == 'spending_summary':
            return self.get_spending_summary(params.get('days', 30))
        
        elif intent == 'top_spending':
            summary = self.get_spending_summary(params.get('days', 30))
            return {
                'top_merchants': summary['top_merchants'],
                'top_categories': summary['top_categories'],
            }
        
        elif intent == 'health_summary':
            return self.get_health_summary()
        
        elif intent == 'compare_test':
            return self.compare_lab_results(params.get('test_name', ''))
        
        elif intent == 'vacation_days':
            return {'free_days': self.find_free_days(params.get('days', 60))}
        
        elif intent == 'upcoming_events':
            return {'events': self.get_calendar_events(params.get('days', 30))}
        
        elif intent == 'suggestions':
            return {'suggestions': self.get_spending_suggestions()}
        
        elif intent == 'month_over_month':
            return self.get_month_over_month()
        
        else:
            return {'error': f'Unknown intent: {intent}'}


# Singleton instance
_data_context: Optional[DataContextService] = None


def get_data_context() -> DataContextService:
    """Get the singleton data context instance."""
    global _data_context
    if _data_context is None:
        _data_context = DataContextService()
    return _data_context
