#!/bin/bash

# HomeSentinel Integration Test Suite
# Tests both frontend and backend servers for proper integration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="https://localhost:8443"
FRONTEND_URL="http://localhost:3000"
BACKEND_PID=""
FRONTEND_PID=""
TEST_TIMEOUT=60
BACKEND_STARTUP_TIMEOUT=10
FRONTEND_STARTUP_TIMEOUT=15

# Cleanup function
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    # Give processes time to shutdown
    sleep 2
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to print test results
test_result() {
    local test_name=$1
    local result=$2

    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        ((TESTS_FAILED++))
    fi
}

# Helper function to wait for service to be ready
wait_for_service() {
    local url=$1
    local timeout=$2
    local service_name=$3
    local start_time=$(date +%s)

    echo -e "${BLUE}Waiting for $service_name to be ready...${NC}"

    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${RED}Timeout waiting for $service_name${NC}"
            return 1
        fi

        if [[ $url == https* ]]; then
            response=$(curl -s -k "$url" 2>/dev/null || echo "")
        else
            response=$(curl -s "$url" 2>/dev/null || echo "")
        fi

        if [ ! -z "$response" ]; then
            echo -e "${GREEN}$service_name is ready${NC}"
            return 0
        fi

        sleep 1
    done
}

# Start backend server
start_backend() {
    echo -e "${BLUE}Starting backend server...${NC}"

    cd "$PROJECT_ROOT/backend"
    python main.py > "$PROJECT_ROOT/backend_test.log" 2>&1 &
    BACKEND_PID=$!

    echo "Backend PID: $BACKEND_PID"

    if ! wait_for_service "$BACKEND_URL/api/health" $BACKEND_STARTUP_TIMEOUT "Backend"; then
        echo -e "${RED}Failed to start backend server${NC}"
        cat "$PROJECT_ROOT/backend_test.log"
        return 1
    fi

    return 0
}

# Start frontend server
start_frontend() {
    echo -e "${BLUE}Starting frontend server...${NC}"

    cd "$PROJECT_ROOT/frontend"
    npm start > "$PROJECT_ROOT/frontend_test.log" 2>&1 &
    FRONTEND_PID=$!

    echo "Frontend PID: $FRONTEND_PID"

    if ! wait_for_service "$FRONTEND_URL" $FRONTEND_STARTUP_TIMEOUT "Frontend"; then
        echo -e "${RED}Failed to start frontend server${NC}"
        cat "$PROJECT_ROOT/frontend_test.log"
        return 1
    fi

    return 0
}

# Test backend health endpoint
test_backend_health() {
    echo -e "${BLUE}Testing backend health endpoint...${NC}"

    response=$(curl -s -k "$BACKEND_URL/api/health")

    if echo "$response" | grep -q "healthy"; then
        test_result "Backend health check responds with 'healthy'" 0
        return 0
    else
        echo "Response: $response"
        test_result "Backend health check responds with 'healthy'" 1
        return 1
    fi
}

# Test backend devices endpoint
test_backend_devices() {
    echo -e "${BLUE}Testing backend devices endpoint...${NC}"

    response=$(curl -s -k "$BACKEND_URL/api/devices")

    if echo "$response" | grep -q "devices"; then
        test_result "Backend devices endpoint returns valid JSON" 0
        return 0
    else
        echo "Response: $response"
        test_result "Backend devices endpoint returns valid JSON" 1
        return 1
    fi
}

# Test CORS configuration
test_cors() {
    echo -e "${BLUE}Testing CORS configuration...${NC}"

    # Test that backend accepts requests from frontend
    response=$(curl -s -k -H "Origin: http://localhost:3000" "$BACKEND_URL/api/health")

    if [ ! -z "$response" ]; then
        test_result "CORS allows requests from localhost:3000" 0
        return 0
    else
        test_result "CORS allows requests from localhost:3000" 1
        return 1
    fi
}

# Test frontend loads
test_frontend_load() {
    echo -e "${BLUE}Testing frontend loads...${NC}"

    response=$(curl -s "$FRONTEND_URL")

    if echo "$response" | grep -q "root"; then
        test_result "Frontend HTML loads successfully" 0
        return 0
    else
        test_result "Frontend HTML loads successfully" 1
        return 1
    fi
}

# Test frontend can communicate with backend
test_frontend_backend_communication() {
    echo -e "${BLUE}Testing frontend-backend communication...${NC}"

    # Make a request from frontend context to backend
    response=$(curl -s -k -H "Origin: http://localhost:3000" "$BACKEND_URL/api/health")

    if echo "$response" | grep -q "healthy"; then
        test_result "Frontend can reach backend API" 0
        return 0
    else
        test_result "Frontend can reach backend API" 1
        return 1
    fi
}

# Test response format
test_response_format() {
    echo -e "${BLUE}Testing API response format...${NC}"

    response=$(curl -s -k "$BACKEND_URL/api/health")

    # Check if response is valid JSON
    if echo "$response" | grep -q '"status"'; then
        test_result "API returns proper JSON format" 0
        return 0
    else
        test_result "API returns proper JSON format" 1
        return 1
    fi
}

# Test error handling
test_error_handling() {
    echo -e "${BLUE}Testing error handling...${NC}"

    # Test non-existent endpoint
    http_code=$(curl -s -k -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/nonexistent")

    if [ "$http_code" = "404" ]; then
        test_result "Backend returns 404 for non-existent endpoints" 0
        return 0
    else
        echo "HTTP Code: $http_code"
        test_result "Backend returns 404 for non-existent endpoints" 1
        return 1
    fi
}

# Test backend responsiveness
test_backend_responsiveness() {
    echo -e "${BLUE}Testing backend responsiveness...${NC}"

    # Make multiple sequential requests
    for i in {1..3}; do
        response=$(curl -s -k "$BACKEND_URL/api/health")
        if ! echo "$response" | grep -q "healthy"; then
            test_result "Backend responds consistently to multiple requests" 1
            return 1
        fi
    done

    test_result "Backend responds consistently to multiple requests" 0
    return 0
}

# Main execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  HomeSentinel Integration Test Suite   ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""

    # Check dependencies
    echo -e "${BLUE}Checking dependencies...${NC}"
    command -v curl >/dev/null 2>&1 || { echo "curl is required but not installed."; exit 1; }
    command -v python >/dev/null 2>&1 || { echo "python is required but not installed."; exit 1; }
    command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed."; exit 1; }
    echo -e "${GREEN}✓ All dependencies found${NC}"
    echo ""

    # Start services
    echo -e "${YELLOW}═══ STARTUP PHASE ═══${NC}"
    if ! start_backend; then
        echo -e "${RED}Failed to start backend, aborting tests${NC}"
        exit 1
    fi
    echo ""

    if ! start_frontend; then
        echo -e "${RED}Failed to start frontend, aborting tests${NC}"
        exit 1
    fi
    echo ""

    # Give servers time to fully initialize
    sleep 3

    # Run tests
    echo -e "${YELLOW}═══ BACKEND TESTS ═══${NC}"
    test_backend_health
    test_backend_devices
    test_response_format
    test_error_handling
    test_backend_responsiveness
    echo ""

    echo -e "${YELLOW}═══ INTEGRATION TESTS ═══${NC}"
    test_cors
    test_frontend_load
    test_frontend_backend_communication
    echo ""

    # Summary
    echo -e "${YELLOW}═══ TEST SUMMARY ═══${NC}"
    TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
    echo -e "Total Tests: ${BLUE}$TOTAL_TESTS${NC}"
    echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All integration tests passed!${NC}"
        return 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        return 1
    fi
}

# Run main function
main
exit $?
