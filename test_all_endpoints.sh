#!/bin/bash

# Comprehensive Test Suite for Avira PLA
# Tests all backend endpoints and frontend functionality

set -e

API_BASE="http://localhost:30000"
FRONTEND_BASE="http://localhost:30001"

echo "=========================================="
echo "AVIRA PLA - COMPREHENSIVE TEST SUITE"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    echo -n "Testing: $name ... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $http_code)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $http_code)"
        echo "  Response: $body"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo "=========================================="
echo "1. HEALTH & SYSTEM CHECKS"
echo "=========================================="

test_endpoint "Backend Health" "GET" "$API_BASE/health"
test_endpoint "Frontend Availability" "GET" "$FRONTEND_BASE"

echo ""
echo "=========================================="
echo "2. ASSISTANT / CHAT ENDPOINTS"
echo "=========================================="

test_endpoint "Assistant Chat" "POST" "$API_BASE/api/assistant/chat" \
    '{"message":"test","session_id":"test123","user_id":"default"}'

test_endpoint "Assistant Sessions List" "GET" "$API_BASE/api/assistant/sessions?user_id=default"

test_endpoint "Privacy Check" "POST" "$API_BASE/api/assistant/privacy/check" \
    '{"text":"My SSN is 123-45-6789"}'

echo ""
echo "=========================================="
echo "3. PORTFOLIO ENDPOINTS"
echo "=========================================="

test_endpoint "Add Portfolio Holding" "POST" "$API_BASE/api/portfolio/holdings" \
    '{"holding_id":"test123","user_id":"default","symbol":"AAPL","shares":10,"average_cost":150,"current_price":180,"total_value":1800,"total_cost":1500,"gain_loss":300,"gain_loss_percent":20,"purchase_date":"2024-01-01","last_updated":"2024-01-01T00:00:00Z"}'

test_endpoint "Get Portfolio Holdings" "GET" "$API_BASE/api/portfolio/holdings?user_id=default"

test_endpoint "Get Stock Info" "GET" "$API_BASE/api/portfolio/stocks/AAPL"

echo ""
echo "=========================================="
echo "4. SHOPPING ENDPOINTS"
echo "=========================================="

test_endpoint "Shopping Search" "POST" "$API_BASE/api/shopping/search" \
    '{"query":"laptop","max_price":1500,"min_rating":4.0}'

test_endpoint "Shopping Compare" "POST" "$API_BASE/api/shopping/compare" \
    '{"query":"laptop","products":[]}'

echo ""
echo "=========================================="
echo "5. TRAVEL ENDPOINTS"
echo "=========================================="

test_endpoint "Flight Search" "POST" "$API_BASE/api/travel/flights" \
    '{"origin":"SFO","destination":"NYC","departure_date":"2024-06-01","return_date":"2024-06-10","passengers":1}'

echo ""
echo "=========================================="
echo "6. HEALTH ENDPOINTS"
echo "=========================================="

test_endpoint "Health Report" "GET" "$API_BASE/api/health/report?user_id=default"

echo ""
echo "=========================================="
echo "7. FINANCE ENDPOINTS"
echo "=========================================="

test_endpoint "Finance Summary" "GET" "$API_BASE/api/finance/summary?user_id=default"

echo ""
echo "=========================================="
echo "8. CALENDAR ENDPOINTS"
echo "=========================================="

test_endpoint "Calendar Events" "GET" "$API_BASE/api/calendar/events?user_id=default"

test_endpoint "Calendar Upcoming" "GET" "$API_BASE/api/calendar/upcoming?days=7"

test_endpoint "Calendar Schools" "GET" "$API_BASE/api/calendar/schools"

test_endpoint "Add Calendar Event" "POST" "$API_BASE/api/calendar/events" \
    '{"event_id":"test123","user_id":"default","title":"Test Event","date":"2024-06-01","time":"10:00","type":"appointment","description":"Test"}'

echo ""
echo "=========================================="
echo "9. SCHOOL ENDPOINTS"
echo "=========================================="

test_endpoint "Schoology Auth URL" "GET" "$API_BASE/api/school/schoology/auth"

test_endpoint "Schoology Status" "GET" "$API_BASE/api/school/schoology/status?user_id=default"

echo ""
echo "=========================================="
echo "10. BILLS ENDPOINTS"
echo "=========================================="

test_endpoint "Bills List" "GET" "$API_BASE/api/bills?user_id=default"

test_endpoint "Bills Summary" "GET" "$API_BASE/api/bills/summary?user_id=default"

echo ""
echo "=========================================="
echo "11. GROCERY ENDPOINTS"
echo "=========================================="

test_endpoint "Grocery List" "GET" "$API_BASE/api/grocery/list?user_id=default"

test_endpoint "Add Grocery Item" "POST" "$API_BASE/api/grocery/items" \
    '{"item_id":"test123","user_id":"default","name":"Milk","quantity":1,"category":"dairy","priority":"medium"}'

echo ""
echo "=========================================="
echo "12. FAMILY ENDPOINTS"
echo "=========================================="

test_endpoint "Family Members" "GET" "$API_BASE/api/family/members?user_id=default"

test_endpoint "Add Family Member" "POST" "$API_BASE/api/family/members" \
    '{"member_id":"test123","user_id":"default","name":"John Doe","relationship":"spouse","birthday":"1990-01-01"}'

echo ""
echo "=========================================="
echo "13. TASKS ENDPOINTS"
echo "=========================================="

test_endpoint "Tasks List" "GET" "$API_BASE/api/tasks?user_id=default"

test_endpoint "Add Task" "POST" "$API_BASE/api/tasks" \
    '{"task_id":"test123","user_id":"default","title":"Test Task","description":"Test","priority":"medium","status":"pending","due_date":"2024-06-01"}'

echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    exit 1
fi
