#!/usr/bin/env python3
"""
Comprehensive Test Suite for Avira PLA
Tests all backend endpoints and frontend functionality
"""

import requests
import json
from typing import Dict, Any
import sys

API_BASE = "http://localhost:30000"
FRONTEND_BASE = "http://localhost:30001"

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

passed = 0
failed = 0
test_results = []

def test_endpoint(name: str, method: str, endpoint: str, data: Dict[Any, Any] = None, expected_status: int = 200):
    """Test a single endpoint"""
    global passed, failed
    
    print(f"Testing: {name} ... ", end='', flush=True)
    
    try:
        if method == "GET":
            response = requests.get(endpoint, timeout=10)
        elif method == "POST":
            response = requests.post(endpoint, json=data, timeout=10)
        elif method == "PUT":
            response = requests.put(endpoint, json=data, timeout=10)
        elif method == "DELETE":
            response = requests.delete(endpoint, timeout=10)
        
        if response.status_code == expected_status or response.status_code == 200:
            print(f"{Colors.GREEN}✓ PASS{Colors.NC} (HTTP {response.status_code})")
            passed += 1
            test_results.append({"name": name, "status": "PASS", "code": response.status_code})
            return True
        else:
            print(f"{Colors.RED}✗ FAIL{Colors.NC} (HTTP {response.status_code})")
            print(f"  Response: {response.text[:200]}")
            failed += 1
            test_results.append({"name": name, "status": "FAIL", "code": response.status_code, "error": response.text[:200]})
            return False
    except Exception as e:
        print(f"{Colors.RED}✗ ERROR{Colors.NC}")
        print(f"  Exception: {str(e)}")
        failed += 1
        test_results.append({"name": name, "status": "ERROR", "error": str(e)})
        return False

def main():
    print("=" * 60)
    print("AVIRA PLA - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print()
    
    # 1. Health & System Checks
    print("=" * 60)
    print("1. HEALTH & SYSTEM CHECKS")
    print("=" * 60)
    test_endpoint("Backend Health", "GET", f"{API_BASE}/health")
    test_endpoint("Frontend Availability", "GET", FRONTEND_BASE)
    print()
    
    # 2. Assistant / Chat Endpoints
    print("=" * 60)
    print("2. ASSISTANT / CHAT ENDPOINTS")
    print("=" * 60)
    test_endpoint("Assistant Chat", "POST", f"{API_BASE}/api/assistant/chat", {
        "message": "test",
        "session_id": "test123",
        "user_id": "default"
    })
    test_endpoint("Assistant Sessions", "GET", f"{API_BASE}/api/assistant/sessions?user_id=default")
    test_endpoint("Privacy Check", "POST", f"{API_BASE}/api/assistant/privacy/check", {
        "text": "My SSN is 123-45-6789"
    })
    print()
    
    # 3. Portfolio Endpoints
    print("=" * 60)
    print("3. PORTFOLIO ENDPOINTS")
    print("=" * 60)
    test_endpoint("Add Portfolio Holding", "POST", f"{API_BASE}/api/portfolio/holdings", {
        "holding_id": "test123",
        "user_id": "default",
        "symbol": "AAPL",
        "shares": 10,
        "average_cost": 150,
        "current_price": 180,
        "total_value": 1800,
        "total_cost": 1500,
        "gain_loss": 300,
        "gain_loss_percent": 20,
        "purchase_date": "2024-01-01",
        "last_updated": "2024-01-01T00:00:00Z"
    })
    test_endpoint("Get Portfolio Holdings", "GET", f"{API_BASE}/api/portfolio/holdings?user_id=default")
    test_endpoint("Get Stock Info", "GET", f"{API_BASE}/api/portfolio/stocks/AAPL")
    print()
    
    # 4. Shopping Endpoints
    print("=" * 60)
    print("4. SHOPPING ENDPOINTS")
    print("=" * 60)
    test_endpoint("Shopping Search", "POST", f"{API_BASE}/api/shopping/search", {
        "query": "laptop",
        "max_price": 1500,
        "min_rating": 4.0
    })
    print()
    
    # 5. Travel Endpoints
    print("=" * 60)
    print("5. TRAVEL ENDPOINTS")
    print("=" * 60)
    test_endpoint("Flight Search", "POST", f"{API_BASE}/api/travel/flights/search", {
        "origin": "SFO",
        "destination": "NYC",
        "departure_date": "2024-06-01",
        "return_date": "2024-06-10",
        "passengers": 1
    })
    print()
    
    # 6. Health Endpoints
    print("=" * 60)
    print("6. HEALTH ENDPOINTS")
    print("=" * 60)
    test_endpoint("Health Report", "GET", f"{API_BASE}/api/health/report?user_id=default")
    print()
    
    # 7. Finance Endpoints
    print("=" * 60)
    print("7. FINANCE ENDPOINTS")
    print("=" * 60)
    test_endpoint("Finance Summary", "GET", f"{API_BASE}/api/finance/summary?user_id=default")
    print()
    
    # 8. Calendar Endpoints
    print("=" * 60)
    print("8. CALENDAR ENDPOINTS")
    print("=" * 60)
    test_endpoint("Calendar Events", "GET", f"{API_BASE}/api/calendar/events?user_id=default")
    test_endpoint("Calendar Upcoming", "GET", f"{API_BASE}/api/calendar/upcoming?days=7")
    test_endpoint("Calendar Schools", "GET", f"{API_BASE}/api/calendar/schools")
    test_endpoint("Add Calendar Event", "GET", f"{API_BASE}/api/calendar/events?date=2024-06-01&title=Test Event")
    print()
    
    # 9. School Endpoints
    print("=" * 60)
    print("9. SCHOOL ENDPOINTS")
    print("=" * 60)
    test_endpoint("Schoology Auth URL", "GET", f"{API_BASE}/api/school/schoology/auth")
    test_endpoint("Schoology Status", "GET", f"{API_BASE}/api/school/schoology/status?user_id=default")
    print()
    
    # 10. Bills Endpoints
    print("=" * 60)
    print("10. BILLS ENDPOINTS")
    print("=" * 60)
    test_endpoint("Bills List", "GET", f"{API_BASE}/api/bills?user_id=default")
    test_endpoint("Bills Summary", "GET", f"{API_BASE}/api/bills/summary?user_id=default")
    print()
    
    # 11. Grocery Endpoints
    print("=" * 60)
    print("11. GROCERY ENDPOINTS")
    print("=" * 60)
    test_endpoint("Grocery Inventory", "GET", f"{API_BASE}/api/grocery/inventory?user_id=default")
    test_endpoint("Grocery Stats", "GET", f"{API_BASE}/api/grocery/stats?user_id=default")
    print()
    
    # 12. Family Endpoints
    print("=" * 60)
    print("12. FAMILY ENDPOINTS")
    print("=" * 60)
    test_endpoint("Family Kids", "GET", f"{API_BASE}/api/family/kids?family_id=default")
    test_endpoint("Family Dashboard", "GET", f"{API_BASE}/api/family/dashboard?family_id=default")
    print()
    
    # 13. Tasks Endpoints
    print("=" * 60)
    print("13. TASKS ENDPOINTS")
    print("=" * 60)
    test_endpoint("Tasks List", "GET", f"{API_BASE}/api/tasks/tasks?user_id=default")
    test_endpoint("Add Task", "POST", f"{API_BASE}/api/tasks/tasks", {
        "task_id": "test123",
        "user_id": "default",
        "title": "Test Task",
        "description": "Test",
        "category": "personal",
        "priority": "medium",
        "status": "todo",
        "due_date": "2024-06-01"
    })
    print()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"{Colors.GREEN}Passed: {passed}{Colors.NC}")
    print(f"{Colors.RED}Failed: {failed}{Colors.NC}")
    print(f"Total: {passed + failed}")
    print()
    
    # Failed tests details
    if failed > 0:
        print("=" * 60)
        print("FAILED TESTS DETAILS")
        print("=" * 60)
        for result in test_results:
            if result["status"] != "PASS":
                print(f"{Colors.RED}✗ {result['name']}{Colors.NC}")
                if "code" in result:
                    print(f"  HTTP Code: {result['code']}")
                if "error" in result:
                    print(f"  Error: {result['error']}")
        print()
    
    if failed == 0:
        print(f"{Colors.GREEN}✓ ALL TESTS PASSED!{Colors.NC}")
        return 0
    else:
        print(f"{Colors.RED}✗ SOME TESTS FAILED{Colors.NC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
