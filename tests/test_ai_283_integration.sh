#!/bin/bash

# Integration Tests for AI-283: Device Detail Card & Dashboard

set -e

BACKEND_URL="https://localhost:8443"
FRONTEND_URL="http://localhost:2026"

echo "=========================================="
echo "AI-283 Integration Tests"
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
echo "Test 2: Device list endpoint returns devices"
if test_api "GET" "/api/devices" "" "200"; then
    ((passed++))
    # Parse response and verify devices have required fields
    devices_response=$(curl -s -X GET "$BACKEND_URL/api/devices" \
        -H "Content-Type: application/json" \
        -k 2>/dev/null)

    # Check if devices array exists and has items
    device_count=$(echo "$devices_response" | grep -o '"device_id"' | wc -l)
    if [ "$device_count" -gt 0 ]; then
        echo "Found $device_count devices"
    else
        echo "Warning: No devices found in response"
    fi
else
    ((failed++))
fi

echo ""
echo "Test 3: Device groups endpoint works"
if test_api "GET" "/api/device-groups" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 4: Single device detail endpoint"
# Get first device ID and test details endpoint
devices_response=$(curl -s -X GET "$BACKEND_URL/api/devices" \
    -H "Content-Type: application/json" \
    -k 2>/dev/null)

first_device_id=$(echo "$devices_response" | grep -o '"device_id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$first_device_id" ]; then
    echo -e "${YELLOW}⊘${NC} No devices found to test detail endpoint"
else
    if test_api "GET" "/api/devices/$first_device_id" "" "200"; then
        ((passed++))
        echo "Device ID: $first_device_id"
    else
        ((failed++))
    fi
fi

echo ""
echo "Test 5: Update device metadata (friendly_name)"
if [ -z "$first_device_id" ]; then
    echo -e "${YELLOW}⊘${NC} Skipping update test - no devices"
else
    update_data='{"friendly_name":"Test Device Updated"}'
    if test_api "PUT" "/api/devices/$first_device_id" "$update_data" "200"; then
        ((passed++))
    else
        ((failed++))
    fi
fi

echo ""
echo "Test 6: Update device type"
if [ -z "$first_device_id" ]; then
    echo -e "${YELLOW}⊘${NC} Skipping device type test - no devices"
else
    update_data='{"device_type":"camera"}'
    if test_api "PUT" "/api/devices/$first_device_id" "$update_data" "200"; then
        ((passed++))
    else
        ((failed++))
    fi
fi

echo ""
echo "Test 7: Update device notes"
if [ -z "$first_device_id" ]; then
    echo -e "${YELLOW}⊘${NC} Skipping notes test - no devices"
else
    update_data='{"notes":"This is a test device"}'
    if test_api "PUT" "/api/devices/$first_device_id" "$update_data" "200"; then
        ((passed++))
    else
        ((failed++))
    fi
fi

echo ""
echo "Test 8: Manual scan trigger"
if test_api "POST" "/api/devices/scan-now" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 9: Check polling configuration"
if test_api "GET" "/api/config/polling" "" "200"; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "Test 10: Device list reflects status"
devices_response=$(curl -s -X GET "$BACKEND_URL/api/devices" \
    -H "Content-Type: application/json" \
    -k 2>/dev/null)

online_count=$(echo "$devices_response" | grep -o '"status":"online"' | wc -l)
offline_count=$(echo "$devices_response" | grep -o '"status":"offline"' | wc -l)

if [ "$online_count" -gt 0 ] || [ "$offline_count" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Device status indicator present"
    echo "  Online: $online_count, Offline: $offline_count"
    ((passed++))
else
    echo -e "${RED}✗${NC} No status indicators found"
    ((failed++))
fi

echo ""
echo "Test 11: Device list has MAC addresses"
mac_count=$(echo "$devices_response" | grep -o '"mac_address"' | wc -l)
if [ "$mac_count" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Device list has MAC addresses ($mac_count devices)"
    ((passed++))
else
    echo -e "${RED}✗${NC} No MAC addresses found in device list"
    ((failed++))
fi

echo ""
echo "Test 12: Device list has IP addresses"
ip_count=$(echo "$devices_response" | grep -o '"current_ip"' | wc -l)
if [ "$ip_count" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Device list has IP addresses"
    ((passed++))
else
    echo -e "${YELLOW}⊘${NC} Warning: No IP addresses in device list"
fi

echo ""
echo "Test 13: Device vendor information"
vendor_count=$(echo "$devices_response" | grep -o '"vendor_name"' | wc -l)
if [ "$vendor_count" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Device vendor information present ($vendor_count devices have vendor)"
    ((passed++))
else
    echo -e "${YELLOW}⊘${NC} Warning: No vendor information in device list"
fi

echo ""
echo "Test 14: Device groups with colors"
groups_response=$(curl -s -X GET "$BACKEND_URL/api/device-groups" \
    -H "Content-Type: application/json" \
    -k 2>/dev/null)

color_count=$(echo "$groups_response" | grep -o '"color":"#[0-9a-fA-F]*"' | wc -l)
if [ "$color_count" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Device groups have colors ($color_count groups)"
    ((passed++))
else
    echo -e "${YELLOW}⊘${NC} Warning: Groups without color information"
fi

echo ""
echo "=========================================="
echo "Integration Test Summary"
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
