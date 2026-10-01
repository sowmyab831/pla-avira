#!/usr/bin/env python3
"""
Comprehensive Regression Testing Suite
Tests all use cases, links, components, and API endpoints
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:30000"
FRONTEND_URL = "http://localhost:30001"

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, test_name: str, details: str = ""):
        self.passed.append((test_name, details))
        print(f"✅ PASS: {test_name}")
        if details:
            print(f"   {details}")
    
    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"❌ FAIL: {test_name}")
        print(f"   Error: {error}")
    
    def add_warning(self, test_name: str, warning: str):
        self.warnings.append((test_name, warning))
        print(f"⚠️  WARN: {test_name}")
        print(f"   {warning}")
    
    def summary(self):
        total = len(self.passed) + len(self.failed)
        print("\n" + "="*70)
        print("COMPREHENSIVE TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {total}")
        print(f"Passed: {len(self.passed)} ({len(self.passed)/total*100:.1f}%)")
        print(f"Failed: {len(self.failed)} ({len(self.failed)/total*100:.1f}%)")
        print(f"Warnings: {len(self.warnings)}")
        print("="*70)
        
        if self.failed:
            print("\n❌ FAILED TESTS:")
            for test, error in self.failed:
                print(f"  - {test}: {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for test, warning in self.warnings:
                print(f"  - {test}: {warning}")
        
        return len(self.failed) == 0

results = TestResults()

def test_health_check():
    """Test 1: Health Check"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()
        if data.get("status") in ["healthy", "degraded"]:
            results.add_pass("Health Check", f"Status: {data.get('status')}")
        else:
            results.add_fail("Health Check", f"Unexpected status: {data.get('status')}")
    except Exception as e:
        results.add_fail("Health Check", str(e))

def test_portfolio_add_holding():
    """Test 2: Portfolio - Add Holding"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/portfolio/holdings",
            json={
                "user_id": "test_regression",
                "symbol": "AAPL",
                "shares": 10,
                "average_cost": 150.00
            },
            timeout=10
        )
        data = response.json()
        if data.get("success"):
            results.add_pass("Portfolio Add Holding", "AAPL added successfully")
        else:
            results.add_fail("Portfolio Add Holding", "Failed to add holding")
    except Exception as e:
        results.add_fail("Portfolio Add Holding", str(e))

def test_portfolio_averaging():
    """Test 3: Portfolio - Averaging Logic"""
    try:
        # Add first holding
        requests.post(
            f"{BASE_URL}/api/portfolio/holdings",
            json={
                "user_id": "test_avg",
                "symbol": "TSLA",
                "shares": 5,
                "average_cost": 200.00
            },
            timeout=10
        )
        
        # Add second holding (should average)
        requests.post(
            f"{BASE_URL}/api/portfolio/holdings",
            json={
                "user_id": "test_avg",
                "symbol": "TSLA",
                "shares": 5,
                "average_cost": 220.00
            },
            timeout=10
        )
        
        # Get holdings
        response = requests.get(
            f"{BASE_URL}/api/portfolio/holdings?user_id=test_avg",
            timeout=10
        )
        data = response.json()
        
        holdings = data.get("holdings", [])
        tsla_holdings = [h for h in holdings if h.get("symbol") == "TSLA"]
        
        if len(tsla_holdings) == 1:
            holding = tsla_holdings[0]
            expected_avg = 210.00  # (200*5 + 220*5) / 10
            actual_avg = holding.get("average_cost")
            
            if abs(actual_avg - expected_avg) < 0.01:
                results.add_pass(
                    "Portfolio Averaging",
                    f"Correctly averaged: 10 shares @ ${actual_avg:.2f}"
                )
            else:
                results.add_fail(
                    "Portfolio Averaging",
                    f"Wrong average: expected ${expected_avg:.2f}, got ${actual_avg:.2f}"
                )
        else:
            results.add_fail(
                "Portfolio Averaging",
                f"Expected 1 TSLA holding, found {len(tsla_holdings)}"
            )
    except Exception as e:
        results.add_fail("Portfolio Averaging", str(e))

def test_portfolio_get_holdings():
    """Test 4: Portfolio - Get Holdings with Real-Time Prices"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/portfolio/holdings?user_id=test_regression",
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("holdings"):
            holding = data["holdings"][0]
            has_price = holding.get("current_price", 0) > 0
            
            if has_price:
                results.add_pass(
                    "Portfolio Get Holdings",
                    f"Real-time price: ${holding.get('current_price'):.2f}"
                )
            else:
                results.add_fail("Portfolio Get Holdings", "No real-time price")
        else:
            results.add_warning("Portfolio Get Holdings", "No holdings found")
    except Exception as e:
        results.add_fail("Portfolio Get Holdings", str(e))

def test_stock_comprehensive_analysis():
    """Test 5: Stock Comprehensive Analysis"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/portfolio/stocks/AAPL/comprehensive",
            timeout=30
        )
        data = response.json()
        
        if data.get("success"):
            has_price = data.get("current_price", 0) > 0
            has_analysis = "analysis" in data
            has_recommendation = "recommendation" in data
            
            if has_price and has_analysis and has_recommendation:
                results.add_pass(
                    "Stock Comprehensive Analysis",
                    f"Price: ${data.get('current_price'):.2f}, "
                    f"Recommendation: {data.get('recommendation')}"
                )
            else:
                missing = []
                if not has_price: missing.append("price")
                if not has_analysis: missing.append("analysis")
                if not has_recommendation: missing.append("recommendation")
                results.add_fail(
                    "Stock Comprehensive Analysis",
                    f"Missing: {', '.join(missing)}"
                )
        else:
            results.add_fail("Stock Comprehensive Analysis", "Request failed")
    except Exception as e:
        results.add_fail("Stock Comprehensive Analysis", str(e))

def test_shopping_search():
    """Test 6: Shopping Search"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/shopping/search",
            json={"query": "laptop", "max_price": 5000, "min_rating": 4.0},
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("products"):
            product_count = len(data["products"])
            first_product = data["products"][0]
            results.add_pass(
                "Shopping Search",
                f"Found {product_count} products. "
                f"First: {first_product['name']} - ${first_product['price']}"
            )
        else:
            results.add_fail("Shopping Search", "No products found")
    except Exception as e:
        results.add_fail("Shopping Search", str(e))

def test_travel_flights():
    """Test 7: Travel Flight Search"""
    try:
        tomorrow = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/travel/flights/search",
            json={
                "origin": "SFO",
                "destination": "JFK",
                "departure_date": tomorrow
            },
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("flights"):
            flight_count = len(data["flights"])
            first_flight = data["flights"][0]
            results.add_pass(
                "Travel Flight Search",
                f"Found {flight_count} flights. "
                f"First: {first_flight['airline']} - ${first_flight['price']}"
            )
        else:
            results.add_fail("Travel Flight Search", "No flights found")
    except Exception as e:
        results.add_fail("Travel Flight Search", str(e))

def test_health_ai_analysis():
    """Test 8: Health AI Analysis"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/health/analyze",
            params={
                "report_text": "Blood pressure 120/80, cholesterol 180 mg/dL",
                "report_type": "blood_test"
            },
            timeout=30
        )
        data = response.json()
        
        if data.get("success") and data.get("analysis"):
            analysis_length = len(data["analysis"])
            has_recommendations = "recommendations" in data
            
            if analysis_length > 100:
                results.add_pass(
                    "Health AI Analysis",
                    f"Analysis: {analysis_length} chars, "
                    f"Has recommendations: {has_recommendations}"
                )
            else:
                results.add_fail(
                    "Health AI Analysis",
                    f"Analysis too short: {analysis_length} chars"
                )
        else:
            results.add_fail("Health AI Analysis", "No analysis returned")
    except Exception as e:
        results.add_fail("Health AI Analysis", str(e))

def test_finance_ai_analysis():
    """Test 9: Finance AI Analysis"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/finance/analyze",
            params={
                "document_text": "Monthly income $5000, expenses $3500",
                "document_type": "bank_statement"
            },
            timeout=30
        )
        data = response.json()
        
        if data.get("success") and data.get("analysis"):
            analysis_length = len(data["analysis"])
            has_recommendations = "recommendations" in data
            
            if analysis_length > 100:
                results.add_pass(
                    "Finance AI Analysis",
                    f"Analysis: {analysis_length} chars, "
                    f"Has recommendations: {has_recommendations}"
                )
            else:
                results.add_fail(
                    "Finance AI Analysis",
                    f"Analysis too short: {analysis_length} chars"
                )
        else:
            results.add_fail("Finance AI Analysis", "No analysis returned")
    except Exception as e:
        results.add_fail("Finance AI Analysis", str(e))

def test_family_management():
    """Test 10: Family Member Management"""
    try:
        # Add member
        response = requests.post(
            f"{BASE_URL}/api/family/members",
            params={"name": "Test User", "age": 30, "gender": "male"},
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("member"):
            member_id = data["member"]["member_id"]
            
            # Get recommendations
            rec_response = requests.get(
                f"{BASE_URL}/api/family/members/{member_id}/recommendations",
                timeout=10
            )
            rec_data = rec_response.json()
            
            if rec_data.get("success") and rec_data.get("recommendations"):
                recs = rec_data["recommendations"]
                health_count = len(recs.get("health", []))
                results.add_pass(
                    "Family Management",
                    f"Member created with {health_count} health recommendations"
                )
            else:
                results.add_fail("Family Management", "No recommendations")
        else:
            results.add_fail("Family Management", "Failed to create member")
    except Exception as e:
        results.add_fail("Family Management", str(e))

def test_nutrition_meal_plan():
    """Test 11: Nutrition Meal Plan"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/nutrition/meal-plan",
            json={
                "age": 30,
                "gender": "male",
                "health_goals": ["weight_loss"]
            },
            timeout=30
        )
        data = response.json()
        
        if data.get("success") and data.get("meal_plan"):
            meal_plan = data["meal_plan"]
            breakfast_count = len(meal_plan.get("breakfast", []))
            lunch_count = len(meal_plan.get("lunch", []))
            dinner_count = len(meal_plan.get("dinner", []))
            
            if breakfast_count >= 3 and lunch_count >= 3 and dinner_count >= 3:
                results.add_pass(
                    "Nutrition Meal Plan",
                    f"Generated: {breakfast_count} breakfast, "
                    f"{lunch_count} lunch, {dinner_count} dinner options"
                )
            else:
                results.add_fail(
                    "Nutrition Meal Plan",
                    f"Insufficient options: {breakfast_count}/{lunch_count}/{dinner_count}"
                )
        else:
            results.add_fail("Nutrition Meal Plan", "No meal plan returned")
    except Exception as e:
        results.add_fail("Nutrition Meal Plan", str(e))

def test_wellness_dashboard():
    """Test 12: Wellness Dashboard"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/wellness/dashboard?user_id=test_regression",
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("overall"):
            overall = data["overall"]
            score = overall.get("score")
            rating = overall.get("rating")
            
            if score is not None and rating:
                results.add_pass(
                    "Wellness Dashboard",
                    f"Score: {score}/100, Rating: {rating}"
                )
            else:
                results.add_fail("Wellness Dashboard", "Missing score or rating")
        else:
            results.add_fail("Wellness Dashboard", "No dashboard data")
    except Exception as e:
        results.add_fail("Wellness Dashboard", str(e))

def test_frontend_accessibility():
    """Test 13: Frontend Accessibility"""
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            results.add_pass("Frontend Accessibility", f"Status: {response.status_code}")
        else:
            results.add_fail("Frontend Accessibility", f"Status: {response.status_code}")
    except Exception as e:
        results.add_fail("Frontend Accessibility", str(e))

def test_stock_news():
    """Test 14: Stock News"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/portfolio/stocks/AAPL/news?limit=5",
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("news"):
            news_count = len(data["news"])
            results.add_pass("Stock News", f"Found {news_count} news articles")
        else:
            results.add_fail("Stock News", "No news found")
    except Exception as e:
        results.add_fail("Stock News", str(e))

def test_stock_sentiment():
    """Test 15: Stock Sentiment Analysis"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/portfolio/stocks/AAPL/sentiment",
            timeout=10
        )
        data = response.json()
        
        if data.get("success") and data.get("sentiment"):
            sentiment = data["sentiment"]
            trend = sentiment.get("sentiment_trend")
            results.add_pass("Stock Sentiment", f"Trend: {trend}")
        else:
            results.add_fail("Stock Sentiment", "No sentiment data")
    except Exception as e:
        results.add_fail("Stock Sentiment", str(e))

def test_portfolio_stats():
    """Test 16: Portfolio Statistics"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/portfolio/stats?user_id=test_regression",
            timeout=10
        )
        data = response.json()
        
        if data.get("success"):
            holdings = data.get("total_holdings", 0)
            results.add_pass("Portfolio Stats", f"Total holdings: {holdings}")
        else:
            results.add_fail("Portfolio Stats", "Failed to get stats")
    except Exception as e:
        results.add_fail("Portfolio Stats", str(e))

def test_stock_alerts():
    """Test 17: Stock Alerts"""
    try:
        # Create alert
        response = requests.post(
            f"{BASE_URL}/api/portfolio/alerts",
            json={
                "user_id": "test_regression",
                "symbol": "AAPL",
                "alert_type": "price_above",
                "target_value": 200.00,
                "is_active": True
            },
            timeout=10
        )
        data = response.json()
        
        if data.get("success"):
            # Get alerts
            get_response = requests.get(
                f"{BASE_URL}/api/portfolio/alerts?user_id=test_regression",
                timeout=10
            )
            get_data = get_response.json()
            
            if get_data.get("success"):
                alert_count = get_data.get("count", 0)
                results.add_pass("Stock Alerts", f"Created and retrieved {alert_count} alerts")
            else:
                results.add_fail("Stock Alerts", "Failed to retrieve alerts")
        else:
            results.add_fail("Stock Alerts", "Failed to create alert")
    except Exception as e:
        results.add_fail("Stock Alerts", str(e))

def test_api_error_handling():
    """Test 18: API Error Handling"""
    try:
        # Test invalid symbol
        response = requests.get(
            f"{BASE_URL}/api/portfolio/stocks/INVALID123/comprehensive",
            timeout=10
        )
        
        # Should handle gracefully, not crash
        if response.status_code in [200, 400, 404]:
            results.add_pass("API Error Handling", "Handles invalid symbol gracefully")
        else:
            results.add_fail("API Error Handling", f"Unexpected status: {response.status_code}")
    except Exception as e:
        results.add_fail("API Error Handling", str(e))

def test_concurrent_requests():
    """Test 19: Concurrent Request Handling"""
    try:
        import concurrent.futures
        
        def make_request():
            return requests.get(f"{BASE_URL}/health", timeout=5)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        success_count = sum(1 for r in responses if r.status_code == 200)
        
        if success_count == 5:
            results.add_pass("Concurrent Requests", "All 5 concurrent requests succeeded")
        else:
            results.add_fail("Concurrent Requests", f"Only {success_count}/5 succeeded")
    except Exception as e:
        results.add_fail("Concurrent Requests", str(e))

def test_response_times():
    """Test 20: Response Time Performance"""
    try:
        import time
        
        start = time.time()
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        elapsed = time.time() - start
        
        if elapsed < 1.0:
            results.add_pass("Response Time", f"Health check: {elapsed*1000:.0f}ms")
        else:
            results.add_warning("Response Time", f"Slow response: {elapsed*1000:.0f}ms")
    except Exception as e:
        results.add_fail("Response Time", str(e))

def main():
    """Run all tests"""
    print("="*70)
    print("COMPREHENSIVE REGRESSION TEST SUITE")
    print("Testing all use cases, links, and components")
    print("="*70)
    print()
    
    # Run all tests
    test_health_check()
    test_portfolio_add_holding()
    test_portfolio_averaging()
    test_portfolio_get_holdings()
    test_stock_comprehensive_analysis()
    test_shopping_search()
    test_travel_flights()
    test_health_ai_analysis()
    test_finance_ai_analysis()
    test_family_management()
    test_nutrition_meal_plan()
    test_wellness_dashboard()
    test_frontend_accessibility()
    test_stock_news()
    test_stock_sentiment()
    test_portfolio_stats()
    test_stock_alerts()
    test_api_error_handling()
    test_concurrent_requests()
    test_response_times()
    
    # Print summary
    success = results.summary()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
