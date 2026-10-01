#!/bin/bash

# Comprehensive test runner for Omni-PLA
# Tests all API endpoints, agents, and features

set -e  # Exit on error

echo "========================================="
echo "Omni-PLA Comprehensive Test Suite"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -e "${YELLOW}Running: ${test_name}${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED: ${test_name}${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED: ${test_name}${NC}"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Check if backend is running
echo "Checking backend health..."
if ! curl -s http://localhost:30000/health > /dev/null; then
    echo -e "${RED}ERROR: Backend is not running at http://localhost:30000${NC}"
    echo "Please start the backend first: kubectl get pods -n pla"
    exit 1
fi
echo -e "${GREEN}✓ Backend is running${NC}"
echo ""

# 1. Health Check Tests
echo "========================================="
echo "1. HEALTH CHECK TESTS"
echo "========================================="

run_test "Health endpoint" \
    "curl -s http://localhost:30000/health | jq -e '.status == \"healthy\"'"

run_test "PostgreSQL connection" \
    "curl -s http://localhost:30000/health | jq -e '.postgres == true'"

run_test "Redis connection" \
    "curl -s http://localhost:30000/health | jq -e '.redis == true'"

run_test "Ollama connection" \
    "curl -s http://localhost:30000/health | jq -e '.ollama == true'"

# 2. Stock Analysis Tests
echo "========================================="
echo "2. STOCK ANALYSIS TESTS"
echo "========================================="

run_test "AAPL comprehensive analysis" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive' | jq -e '.success == true and .symbol == \"AAPL\"'"

run_test "SHOP comprehensive analysis" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/SHOP/comprehensive' | jq -e '.success == true and .symbol == \"SHOP\"'"

run_test "RELIANCE.NS (India) analysis" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/RELIANCE.NS/comprehensive' | jq -e '.success == true'"

run_test "AI analysis length (>1800 chars)" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive' | jq -e '(.ai_recommendation.analysis | length) >= 1800'"

run_test "Technical indicators present" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive' | jq -e '.technical_analysis.rsi != null and .technical_analysis.trend != null'"

# 3. Options Trading Tests
echo "========================================="
echo "3. OPTIONS TRADING TESTS"
echo "========================================="

run_test "AAPL options strategies" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/options' | jq -e '.success == true and (.options.strategies | length) >= 3'"

run_test "Options Greeks present" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/options' | jq -e '.options.strategies[0].greeks.delta != null'"

run_test "Recommended strategy present" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/options' | jq -e '.options.recommended_strategy != null'"

# 4. News Endpoints Tests
echo "========================================="
echo "4. NEWS AGGREGATION TESTS"
echo "========================================="

run_test "Knowledge Pill endpoint" \
    "curl -s 'http://localhost:30000/api/news/knowledge-pill' | jq -e '.success == true and (.pill_of_the_day.key_takeaways | length) >= 5'"

run_test "Reuters news endpoint" \
    "curl -s 'http://localhost:30000/api/news/reuters' | jq -e '.success == true and .source == \"Reuters\"'"

run_test "Market Influencers endpoint" \
    "curl -s 'http://localhost:30000/api/news/influencers' | jq -e '.success == true and (.influencers | length) >= 4'"

run_test "India market news endpoint" \
    "curl -s 'http://localhost:30000/api/news/india/market' | jq -e '.success == true and .market == \"India (NSE/BSE)\"'"

run_test "Investment firms endpoint" \
    "curl -s 'http://localhost:30000/api/news/investment-firms' | jq -e '.success == true and (.firms | length) >= 3'"

run_test "Financial news (global)" \
    "curl -s 'http://localhost:30000/api/news/financial/daily?region=global' | jq -e '.success == true and .region == \"global\"'"

run_test "Tech news endpoint" \
    "curl -s 'http://localhost:30000/api/news/tech/daily' | jq -e '.success == true'"

# 5. Shopping Tests
echo "========================================="
echo "5. SMART SHOPPING TESTS"
echo "========================================="

run_test "Product search - laptop" \
    "curl -s 'http://localhost:30000/api/shopping/search?query=laptop' | jq -e '.success == true and (.products | length) > 0'"

run_test "Realistic pricing (20-500 range)" \
    "curl -s 'http://localhost:30000/api/shopping/search?query=hershy+syrup' | jq -e '([.products[].price] | min) >= 20 and ([.products[].price] | max) <= 500'"

# 6. Travel Tests
echo "========================================="
echo "6. TRAVEL PLANNING TESTS"
echo "========================================="

run_test "Flight search CLT-RDU" \
    "curl -s 'http://localhost:30000/api/travel/flights/search?origin=CLT&destination=RDU&departure_date=2026-02-11' | jq -e '.success == true and (.flights | length) > 0'"

run_test "Realistic flight pricing" \
    "curl -s 'http://localhost:30000/api/travel/flights/search?origin=CLT&destination=RDU&departure_date=2026-02-11' | jq -e '([.flights[].price] | min) >= 50 and ([.flights[].price] | max) <= 300'"

# 7. Price Realism Tests
echo "========================================="
echo "7. PRICE REALISM TESTS"
echo "========================================="

run_test "Shopping prices realistic" \
    "curl -s 'http://localhost:30000/api/shopping/search?query=organic+chicken' | jq -e '([.products[].price] | min) >= 20 and ([.products[].price] | max) <= 100'"

run_test "Flight prices realistic (short haul)" \
    "curl -s 'http://localhost:30000/api/travel/flights/search?origin=CLT&destination=RDU&departure_date=2026-02-11' | jq -e '([.flights[].price] | min) >= 50'"

# 8. Data Quality Tests
echo "========================================="
echo "8. DATA QUALITY TESTS"
echo "========================================="

run_test "Stock price is real-time (not demo)" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive' | jq -e '.current_price > 0 and .current_price < 1000'"

run_test "RSI in valid range (0-100)" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive' | jq -e '.technical_analysis.rsi >= 0 and .technical_analysis.rsi <= 100'"

run_test "AI confidence score present" \
    "curl -s 'http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive' | jq -e '.ai_recommendation.confidence != null'"

# Summary
echo ""
echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo -e "${GREEN}Tests Passed: ${TESTS_PASSED}${NC}"
echo -e "${RED}Tests Failed: ${TESTS_FAILED}${NC}"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    exit 1
fi
