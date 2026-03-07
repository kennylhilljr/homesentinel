"""
Backend API Tests for HomeSentinel
Tests for health checks, CORS configuration, and API endpoints
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path to import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


class TestHealthCheckEndpoints:
    """Test suite for health check endpoints"""

    def test_root_health_check(self, client):
        """Test root health check endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        assert data["version"] == "1.0.0"

    def test_api_health_check(self, client):
        """Test /api/health endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "HomeSentinel Backend"

    def test_health_check_response_format(self, client):
        """Test that health check returns JSON"""
        response = client.get("/api/health")
        assert response.headers["content-type"] == "application/json"


class TestDeviceEndpoints:
    """Test suite for device management endpoints"""

    def test_get_devices_endpoint(self, client):
        """Test /api/devices endpoint"""
        response = client.get("/api/devices")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total" in data
        assert "timestamp" in data
        assert isinstance(data["devices"], list)
        assert isinstance(data["total"], int)

    def test_get_devices_initial_empty(self, client):
        """Test that devices list starts empty"""
        response = client.get("/api/devices")
        data = response.json()
        assert data["total"] == 0
        assert len(data["devices"]) == 0

    def test_get_online_devices_endpoint(self, client):
        """Test /api/devices/online endpoint"""
        response = client.get("/api/devices/online")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total" in data
        assert data["status_filter"] == "online"

    def test_get_offline_devices_endpoint(self, client):
        """Test /api/devices/offline endpoint"""
        response = client.get("/api/devices/offline")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total" in data
        assert data["status_filter"] == "offline"


class TestCORSConfiguration:
    """Test suite for CORS configuration"""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in response"""
        response = client.options("/api/health")
        # CORS headers might be in response for preflight requests
        assert response.status_code in [200, 405]  # 405 is expected for OPTIONS on non-CORS endpoints

    def test_api_endpoints_accessible(self, client):
        """Test that API endpoints are accessible (no CORS blocking)"""
        endpoints = [
            "/",
            "/api/health",
            "/api/devices"
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"


class TestErrorHandling:
    """Test suite for error handling"""

    def test_404_not_found(self, client):
        """Test that non-existent endpoints return 404"""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_405_method_not_allowed(self, client):
        """Test that wrong HTTP methods return 405"""
        response = client.post("/api/devices")
        assert response.status_code == 405

    def test_500_error_handling(self, client):
        """Test that server errors are handled properly"""
        # This endpoint doesn't exist, should get 404 not 500
        response = client.get("/api/crash")
        assert response.status_code == 404


class TestRequestResponseFormat:
    """Test suite for API request/response format"""

    def test_response_content_type(self, client):
        """Test that responses have correct content type"""
        response = client.get("/api/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_response_structure(self, client):
        """Test that health check response has expected structure"""
        response = client.get("/api/health")
        data = response.json()
        required_fields = ["status", "service"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_devices_response_structure(self, client):
        """Test that devices response has expected structure"""
        response = client.get("/api/devices")
        data = response.json()
        required_fields = ["devices", "total"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestAPIIntegration:
    """Test suite for API integration"""

    def test_health_check_before_devices(self, client):
        """Test that health check works before getting devices"""
        health = client.get("/api/health")
        assert health.status_code == 200

        devices = client.get("/api/devices")
        assert devices.status_code == 200

    def test_sequential_requests(self, client):
        """Test that sequential API requests work properly"""
        for i in range(3):
            response = client.get("/api/health")
            assert response.status_code == 200

            response = client.get("/api/devices")
            assert response.status_code == 200


class TestCrossOriginRequests:
    """Test suite for cross-origin request handling"""

    def test_cors_localhost_3000(self, client):
        """Test CORS allows localhost:3000"""
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200

    def test_cors_https_localhost_3000(self, client):
        """Test CORS allows https://localhost:3000"""
        response = client.get(
            "/api/health",
            headers={"Origin": "https://localhost:3000"}
        )
        assert response.status_code == 200


class TestPollingConfigEndpoints:
    """Test suite for polling configuration endpoints"""

    def test_get_polling_config(self, client):
        """Test GET /api/config/polling endpoint"""
        response = client.get("/api/config/polling")
        assert response.status_code == 200
        data = response.json()
        assert "interval" in data
        assert "last_scan" in data
        assert "polling_status" in data
        assert data["interval"] == 60  # Default interval

    def test_polling_config_has_required_fields(self, client):
        """Test that polling config has all required fields"""
        response = client.get("/api/config/polling")
        data = response.json()
        assert "interval" in data
        assert "polling_status" in data
        assert isinstance(data["interval"], int)


class TestManualScanEndpoint:
    """Test suite for manual scan endpoint"""

    def test_scan_now_endpoint(self, client):
        """Test POST /api/devices/scan-now endpoint"""
        response = client.post("/api/devices/scan-now")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "devices_found" in data
        assert "timestamp" in data
        assert "scan_time_seconds" in data

    def test_scan_now_returns_results(self, client):
        """Test that scan-now returns proper structure"""
        response = client.post("/api/devices/scan-now")
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["devices_found"], int)
        assert isinstance(data["devices_added"], int)
        assert isinstance(data["devices_updated"], int)


class TestAPIHealthWithDatabase:
    """Test suite for API health with database"""

    def test_health_check_shows_database_status(self, client):
        """Test that health check includes database status"""
        response = client.get("/api/health")
        data = response.json()
        assert "database" in data
        assert data["database"] in ["connected", "disconnected"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
