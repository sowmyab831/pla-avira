#!/usr/bin/env python3
"""
Comprehensive End-to-End Testing with Real Internet Data
Tests all backend endpoints and verifies real-time data fetching
"""

import requests
import json
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:30000"
FRONTEND_URL = "http://localhost:30001"

def print_test(name, status, details=""):
    """Print test result."""
    symbol = "✅" if status else "❌"
    print(f"{symbol} {name}")
    if details:
        print(f"   {details}")
    print()

def test_health():
    """Test health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()
        success = data.get("status") == "healthy" or data.get("status") == "degraded"
        print_test("Health Check", success, f"Status: {data.get('status')}")
        return success
    except Exception as e:
        print_test("Health Check", False, str(e))
        return False

def test_portfolio_real_data():
    """Test portfolio with real Yahoo Finance data."""
    try:
        # Add a holding
        response = requests.post(
            f"{BASE_URL}/api/portfolio/holdings",
            json={
                "user_id": "test_user",
                "symbol": "AAPL",
                "shares": 10,
                "average_cost": 150.00
            },
            timeout=10
        )
        
        # Get holdings with real-time prices
        response = requests.get(
            f"{BASE_URL}/api/portfolio/holdings?user_id=test_user",
            timeout=10
        )
        data = response.json()
        
        if data.get("holdings"):
            holding = data["holdings"][0]
            has_real_price = holding.get("current_price", 0) > 0
            print_test(
                "Portfolio Real-Time Data",
                has_real_price,
                f"AAPL Price: ${holding.get('current_price', 0):.2f}"
            )
            return has_real_price
        else:
            print_test("Portfolio Real-Time Data", False, "No holdings returned")
            return False
    except Exception as e:
        print_test("Portfolio Real-Time Data", False, str(e))
        return False

def test_shopping_search():
    """Test shopping search with real results."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/shopping/search",
            json={"query": "laptop", "max_price": 5000, "min_rating": 4.0},
            timeout=10
        )
        data = response.json()
        
        has_products = data.get("success") and len(data.get("products", [])) > 0
        product_count = len(data.get("products", []))
        
        if has_products:
            product = data["products"][0]
            print_test(
                "Shopping Search",
                True,
                f"Found {product_count} products. First: {product['name']} - ${product['price']}"
            )
        else:
            print_test("Shopping Search", False, "No products found")
        
        return has_products
    except Exception as e:
        print_test("Shopping Search", False, str(e))
        return False

def test_travel_flights():
    """Test travel flight search."""
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
        
        has_flights = data.get("success") and len(data.get("flights", [])) > 0
        flight_count = len(data.get("flights", []))
        
        if has_flights:
            flight = data["flights"][0]
            print_test(
                "Travel Flight Search",
                True,
                f"Found {flight_count} flights. First: {flight['airline']} - ${flight['price']}"
            )
        else:
            print_test("Travel Flight Search", False, "No flights found")
        
        return has_flights
    except Exception as e:
        print_test("Travel Flight Search", False, str(e))
        return False

def test_health_ai_analysis():
    """Test health AI analysis."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/health/analyze",
            params={
                "report_text": "Blood pressure 120/80, cholesterol 180 mg/dL, glucose 95 mg/dL",
                "report_type": "blood_test"
            },
            timeout=30
        )
        data = response.json()
        
        has_analysis = data.get("success") and "analysis" in data
        
        if has_analysis:
            print_test(
                "Health AI Analysis",
                True,
                f"Analysis length: {len(data.get('analysis', ''))} chars"
            )
        else:
            print_test("Health AI Analysis", False, "No analysis returned")
        
        return has_analysis
    except Exception as e:
        print_test("Health AI Analysis", False, str(e))
        return False

def test_finance_ai_analysis():
    """Test finance AI analysis."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/finance/analyze",
            params={
                "document_text": "Monthly income $5000, expenses $3500, savings $1000",
                "document_type": "bank_statement"
            },
            timeout=30
        )
        data = response.json()
        
        has_analysis = data.get("success") and "analysis" in data
        
        if has_analysis:
            print_test(
                "Finance AI Analysis",
                True,
                f"Analysis length: {len(data.get('analysis', ''))} chars"
            )
        else:
            print_test("Finance AI Analysis", False, "No analysis returned")
        
        return has_analysis
    except Exception as e:
        print_test("Finance AI Analysis", False, str(e))
        return False

def test_family_management():
    """Test family member management."""
    try:
        # Add family member
        response = requests.post(
            f"{BASE_URL}/api/family/members",
            params={
                "name": "John Doe",
                "age": 35,
                "gender": "male"
            },
            timeout=10
        )
        data = response.json()
        
        member_id = data.get("member", {}).get("member_id")
        
        if member_id:
            # Get recommendations
            response = requests.get(
                f"{BASE_URL}/api/family/members/{member_id}/recommendations",
                timeout=10
            )
            rec_data = response.json()
            
            has_recommendations = rec_data.get("success") and "recommendations" in rec_data
            
            if has_recommendations:
                recs = rec_data["recommendations"]
                print_test(
                    "Family Management",
                    True,
                    f"Member created with {len(recs.get('health', []))} health recommendations"
                )
            else:
                print_test("Family Management", False, "No recommendations returned")
            
            return has_recommendations
        else:
            print_test("Family Management", False, "Failed to create member")
            return False
    except Exception as e:
        print_test("Family Management", False, str(e))
        return False

def test_nutrition_meal_plan():
    """Test nutrition meal plan generation."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/nutrition/meal-plan",
            json={
                "age": 30,
                "gender": "male",
                "health_goals": ["weight_loss"],
                "dietary_preferences": None,
                "allergies": None
            },
            timeout=30
        )
        data = response.json()
        
        has_meal_plan = data.get("success") and "meal_plan" in data
        
        if has_meal_plan:
            meal_plan = data["meal_plan"]
            breakfast_count = len(meal_plan.get("breakfast", []))
            print_test(
                "Nutrition Meal Plan",
                True,
                f"Generated meal plan with {breakfast_count} breakfast options"
            )
        else:
            print_test("Nutrition Meal Plan", False, "No meal plan returned")
        
        return has_meal_plan
    except Exception as e:
        print_test("Nutrition Meal Plan", False, str(e))
        return False

def test_wellness_dashboard():
    """Test wellness dashboard."""
    try:
        response = requests.get(
            f"{BASE_URL}/api/wellness/dashboard?user_id=test_user",
            timeout=10
        )
        data = response.json()
        
        has_dashboard = data.get("success") and "overall" in data
        
        if has_dashboard:
            overall = data["overall"]
            print_test(
                "Wellness Dashboard",
                True,
                f"Overall score: {overall.get('score')}/100 - {overall.get('rating')}"
            )
        else:
            print_test("Wellness Dashboard", False, "No dashboard data returned")
        
        return has_dashboard
    except Exception as e:
        print_test("Wellness Dashboard", False, str(e))
        return False

def test_frontend_accessibility():
    """Test frontend is accessible."""
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        success = response.status_code == 200
        print_test("Frontend Accessibility", success, f"Status: {response.status_code}")
        return success
    except Exception as e:
        print_test("Frontend Accessibility", False, str(e))
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("COMPREHENSIVE END-TO-END TESTING")
    print("Testing with Real Internet Data")
    print("=" * 60)
    print()
    
    results = {}
    
    # Run all tests
    results["Health Check"] = test_health()
    results["Portfolio Real-Time Data"] = test_portfolio_real_data()
    results["Shopping Search"] = test_shopping_search()
    results["Travel Flight Search"] = test_travel_flights()
    results["Health AI Analysis"] = test_health_ai_analysis()
    results["Finance AI Analysis"] = test_finance_ai_analysis()
    results["Family Management"] = test_family_management()
    results["Nutrition Meal Plan"] = test_nutrition_meal_plan()
    results["Wellness Dashboard"] = test_wellness_dashboard()
    results["Frontend Accessibility"] = test_frontend_accessibility()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Passed: {passed}/{total} ({passed/total*100:.1f}%)")
    print()
    
    for test_name, result in results.items():
        symbol = "✅" if result else "❌"
        print(f"{symbol} {test_name}")
    
    print()
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"⚠️  {total - passed} TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
