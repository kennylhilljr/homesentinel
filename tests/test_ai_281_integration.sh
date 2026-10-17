#!/bin/bash

# Integration Tests for AI-281: OUI Vendor Lookup & Device Registry

set -e

BACKEND_URL="https://localhost:8443"
FRONTEND_URL="http://localhost:2026"

echo "=========================================="
echo "AI-281 Integration Tests"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed=0
failed=0

# Helper function to test API
test_api() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_code=$4

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BACKEND_URL$endpoint" \
            -H "Content-Type: application/json" \
            -k 2>/dev/null || echo "000")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BACKEND_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data" \
            -k 2>/dev/null || echo "000")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "$expected_code" ]; then
        echo -e "${GREEN}✓${NC} $method $endpoint (HTTP $http_code)"
        echo "$body"
        return 0
    else
        echo -e "${RED}✗${NC} $method $endpoint (Expected $expected_code, got $http_code)"
        echo "$body"
        return 1
    fi
}

echo ""
echo "Test 1: Backend is running and healthy"
if test_api "GET" "/api/health" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 2: Device list endpoint works"
if test_api "GET" "/api/devices" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 3: Create device group"
group_data='{"name":"Living Room","color":"#3498db"}'
if test_api "POST" "/api/device-groups" "$group_data" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 4: List device groups"
if test_api "GET" "/api/device-groups" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 5: Manual scan trigger"
if test_api "POST" "/api/devices/scan-now" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 6: Check polling config"
if test_api "GET" "/api/config/polling" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}$passed${NC}"
echo -e "Failed: ${RED}$failed${NC}"
echo "=========================================="

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All integration tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
