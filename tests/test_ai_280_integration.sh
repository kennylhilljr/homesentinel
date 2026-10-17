#!/bin/bash

# Integration tests for AI-280: LAN Device Discovery via ARP/DHCP
# Tests the complete flow of device discovery, database persistence, and API endpoints

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Log function
log() {
    echo -e "${GREEN}[TEST]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

# Check if backend is running
check_backend() {
    log "Checking backend health..."
    for i in {1..30}; do
        if curl -s -k https://localhost:8443/api/health > /dev/null 2>&1; then
            success "Backend is running"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    error "Backend did not start in time"
    return 1
}

# Check if frontend is running
check_frontend() {
    log "Checking frontend health..."
    for i in {1..30}; do
        if curl -s http://localhost:2026 > /dev/null 2>&1; then
            success "Frontend is running"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    error "Frontend did not start in time"
    return 1
}

# Test database initialization
test_database_init() {
    log "Testing database initialization..."
    if [ -f "$BACKEND_DIR/homesentinel.db" ]; then
        success "Database file created"
    else
        error "Database file not found"
        return 1
    fi

    # Check tables exist
    sqlite3 "$BACKEND_DIR/homesentinel.db" "SELECT name FROM sqlite_master WHERE type='table' AND name='network_devices';" > /dev/null
    if [ $? -eq 0 ]; then
        success "network_devices table exists"
    else
        error "network_devices table not found"
        return 1
    fi

    sqlite3 "$BACKEND_DIR/homesentinel.db" "SELECT name FROM sqlite_master WHERE type='table' AND name='polling_config';" > /dev/null
    if [ $? -eq 0 ]; then
        success "polling_config table exists"
    else
        error "polling_config table not found"
        return 1
    fi
}

# Test API endpoints
test_api_health() {
    log "Testing API health endpoint..."
    response=$(curl -s -k https://localhost:8443/api/health)
    if echo "$response" | grep -q "healthy"; then
        success "Health endpoint returns proper status"
    else
        error "Health endpoint response invalid: $response"
        return 1
    fi
}

test_get_devices() {
    log "Testing GET /api/devices endpoint..."
    response=$(curl -s -k https://localhost:8443/api/devices)
    if echo "$response" | grep -q '"devices"'; then
        success "GET /api/devices returns devices array"
    else
        error "GET /api/devices response invalid: $response"
        return 1
    fi
}

test_get_polling_config() {
    log "Testing GET /api/config/polling endpoint..."
    response=$(curl -s -k https://localhost:8443/api/config/polling)
    if echo "$response" | grep -q '"interval"'; then
        success "GET /api/config/polling returns interval"
    else
        error "GET /api/config/polling response invalid: $response"
        return 1
    fi
}

test_manual_scan() {
    log "Testing POST /api/devices/scan-now endpoint..."
    response=$(curl -s -k -X POST https://localhost:8443/api/devices/scan-now)
    if echo "$response" | grep -q '"success"'; then
        success "Manual scan endpoint works"
    else
        error "Manual scan response invalid: $response"
        return 1
    fi

    if echo "$response" | grep -q '"devices_found"'; then
        success "Manual scan returns devices_found"
    else
        error "Manual scan missing devices_found"
        return 1
    fi
}

test_polling_interval() {
    log "Testing polling interval configuration..."
    response=$(curl -s -k https://localhost:8443/api/config/polling)
    interval=$(echo "$response" | grep -o '"interval":[0-9]*' | cut -d':' -f2)
    if [ "$interval" == "60" ]; then
        success "Default polling interval is 60 seconds"
    else
        error "Polling interval is not 60: $interval"
        return 1
    fi
}

test_device_list_structure() {
    log "Testing device list response structure..."
    response=$(curl -s -k https://localhost:8443/api/devices)

    # Check required fields
    for field in "devices" "total" "timestamp"; do
        if echo "$response" | grep -q "\"$field\""; then
            success "Device response contains $field"
        else
            error "Device response missing $field"
            return 1
        fi
    done
}

test_online_offline_devices() {
    log "Testing online/offline device filtering..."
    response=$(curl -s -k https://localhost:8443/api/devices/online)
    if echo "$response" | grep -q '"status_filter":"online"'; then
        success "Online devices endpoint works"
    else
        error "Online devices endpoint response invalid"
        return 1
    fi

    response=$(curl -s -k https://localhost:8443/api/devices/offline)
    if echo "$response" | grep -q '"status_filter":"offline"'; then
        success "Offline devices endpoint works"
    else
        error "Offline devices endpoint response invalid"
        return 1
    fi
}

# Test frontend
test_frontend_load() {
    log "Testing frontend loads..."
    response=$(curl -s http://localhost:2026)
    if echo "$response" | grep -q "HomeSentinel"; then
        success "Frontend loads successfully"
    else
        error "Frontend did not load properly"
        return 1
    fi
}

test_frontend_api_calls() {
    log "Testing frontend can call API..."
    # Just verify the frontend HTML contains references to the API endpoints
    response=$(curl -s http://localhost:2026)
    if echo "$response" | grep -q "api/devices"; then
        success "Frontend references API endpoints"
    else
        error "Frontend missing API endpoint references"
        return 1
    fi
}

# Run all tests
main() {
    echo "========================================="
    echo "AI-280 Integration Tests"
    echo "LAN Device Discovery via ARP/DHCP"
    echo "========================================="
    echo ""

    # Verify backends are running
    if ! check_backend; then
        echo ""
        echo "Note: Backend should be running. Start with:"
        echo "  cd $BACKEND_DIR && python main.py"
        return 1
    fi

    if ! check_frontend; then
        echo ""
        echo "Note: Frontend should be running. Start with:"
        echo "  cd $FRONTEND_DIR && npm start"
        return 1
    fi

    echo ""
    log "Running integration tests..."
    echo ""

    # Run tests
    test_database_init
    test_api_health
    test_get_devices
    test_get_polling_config
    test_polling_interval
    test_device_list_structure
    test_get_devices
    test_manual_scan
    test_online_offline_devices
    test_frontend_load
    test_frontend_api_calls

    echo ""
    echo "========================================="
    echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
    fi
    echo "========================================="

    if [ $TESTS_FAILED -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

main "$@"
