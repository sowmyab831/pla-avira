#!/bin/bash

echo "=========================================="
echo "TESTING ALL AVIRA FEATURES"
echo "=========================================="
echo ""

BASE_URL="http://localhost:30000"
FAILED_TESTS=()
PASSED_TESTS=()

test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    
    echo "Testing: $name"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$BASE_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo "✅ PASSED ($http_code)"
        PASSED_TESTS+=("$name")
    else
        echo "❌ FAILED ($http_code)"
        echo "Response: $body"
        FAILED_TESTS+=("$name")
    fi
    echo ""
}

echo "1. HEALTH CHECK"
echo "----------------------------------------"
test_endpoint "Backend Health" "GET" "/health" ""

echo "2. AUTHENTICATION"
echo "----------------------------------------"
test_endpoint "Init Admin" "POST" "/api/auth/init-admin" ""
test_endpoint "Admin Login" "POST" "/api/auth/login" '{"username":"admin","password":"changeme"}'

echo "3. PORTFOLIO / INVESTMENT"
echo "----------------------------------------"
test_endpoint "Get Holdings" "GET" "/api/portfolio/holdings?user_id=test" ""
test_endpoint "Add Holding" "POST" "/api/portfolio/holdings" '{"user_id":"test","symbol":"AAPL","shares":10,"average_cost":150.00}'
test_endpoint "Stock Quote" "GET" "/api/portfolio/stocks/AAPL/quote" ""
test_endpoint "Stock History" "GET" "/api/portfolio/stocks/AAPL/history?period=1M" ""
test_endpoint "Stock Analysis" "POST" "/api/portfolio/stocks/AAPL/analyze" '{"user_id":"test"}'

echo "4. SHOPPING"
echo "----------------------------------------"
test_endpoint "Search Products - Laptop" "GET" "/api/shopping/search?query=laptop" ""
test_endpoint "Search Products - Phone" "GET" "/api/shopping/search?query=iphone" ""
test_endpoint "Get Deals" "GET" "/api/shopping/deals" ""

echo "5. TRAVEL"
echo "----------------------------------------"
test_endpoint "Search Flights" "GET" "/api/travel/flights/search?origin=SFO&destination=JFK&departure_date=2026-03-15" ""
test_endpoint "Search Hotels" "GET" "/api/travel/hotels/search?location=San%20Francisco&checkin=2026-03-15&checkout=2026-03-17" ""

echo "6. AI ASSISTANT"
echo "----------------------------------------"
test_endpoint "Chat - Investment Query" "POST" "/api/assistant/chat" '{"message":"should I buy AAPL stock?","user_id":"test"}'
test_endpoint "Chat - Shopping Query" "POST" "/api/assistant/chat" '{"message":"where can I buy a laptop?","user_id":"test"}'
test_endpoint "Chat - Travel Query" "POST" "/api/assistant/chat" '{"message":"flights from SFO to NYC","user_id":"test"}'
test_endpoint "Get Sessions" "GET" "/api/assistant/sessions/test" ""

echo "7. CALENDAR"
echo "----------------------------------------"
test_endpoint "Get Events" "GET" "/api/calendar/events" ""
test_endpoint "Get Upcoming" "GET" "/api/calendar/upcoming?days=30" ""
test_endpoint "Create Event" "POST" "/api/calendar/events" '{"date":"2026-02-14","title":"Test Event","type":"custom"}'
test_endpoint "Get Schools" "GET" "/api/calendar/schools" ""

echo "8. WELLNESS"
echo "----------------------------------------"
test_endpoint "Get Wellness Summary" "GET" "/api/wellness/summary?user_id=test" ""
test_endpoint "Log Activity" "POST" "/api/wellness/activity" '{"user_id":"test","activity_type":"running","duration_minutes":30,"calories":300}'

echo "9. NUTRITION"
echo "----------------------------------------"
test_endpoint "Analyze Meal" "POST" "/api/nutrition/analyze" '{"user_id":"test","meal_description":"chicken salad with vegetables"}'
test_endpoint "Get Nutrition Summary" "GET" "/api/nutrition/summary?user_id=test" ""

echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo "Passed: ${#PASSED_TESTS[@]}"
echo "Failed: ${#FAILED_TESTS[@]}"
echo ""

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo "Failed Tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
    exit 1
else
    echo "✅ ALL TESTS PASSED!"
    exit 0
fi
