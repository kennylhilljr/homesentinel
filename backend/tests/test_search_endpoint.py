"""
Integration tests for Device Search API endpoint
"""

import pytest
import os
import sys
import tempfile
import json
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from db import Database, NetworkDeviceRepository


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    db.run_migrations()
    yield db
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(temp_db):
    """Create test client"""
    # Override DB for testing
    import main
    main.db = temp_db
    main.search_service = main.DeviceSearchService(temp_db)

    # Create test devices
    repo = NetworkDeviceRepository(temp_db)

    # Device 1
    dev1 = repo.create_or_update("device-1", "b8:27:eb:aa:bb:cc", "192.168.1.100")
    repo.update_device_metadata(dev1['device_id'],
        friendly_name="Raspberry Pi",
        vendor_name="Raspberry PI"
    )

    # Device 2
    dev2 = repo.create_or_update("device-2", "00:0c:29:aa:bb:dd", "192.168.1.1")
    repo.update_device_metadata(dev2['device_id'],
        friendly_name="Network Router",
        vendor_name="CISCO"
    )

    # Device 3
    dev3 = repo.create_or_update("device-3", "aa:bb:cc:dd:ee:ff", "192.168.1.150")
    repo.update_device_metadata(dev3['device_id'],
        friendly_name="Mobile Phone",
        vendor_name="APPLE"
    )

    return TestClient(app)


class TestSearchEndpoint:
    """Tests for /api/devices/search endpoint"""

    def test_search_empty_query(self, client):
        """Test search with empty query returns error"""
        response = client.get("/api/devices/search?q=")
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()

    def test_search_no_query_param(self, client):
        """Test search without query parameter"""
        response = client.get("/api/devices/search")
        assert response.status_code == 400

    def test_search_by_mac(self, client):
        """Test search by MAC address"""
        response = client.get("/api/devices/search?q=b8:27")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "query" in data
        assert "total" in data
        assert len(data["devices"]) >= 1

    def test_search_by_ip(self, client):
        """Test search by IP address"""
        response = client.get("/api/devices/search?q=192.168.1.1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) >= 1

    def test_search_by_ip_prefix(self, client):
        """Test search by IP prefix"""
        response = client.get("/api/devices/search?q=192.168")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) >= 2

    def test_search_by_friendly_name(self, client):
        """Test search by friendly name"""
        response = client.get("/api/devices/search?q=raspberry")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) >= 1

    def test_search_by_vendor(self, client):
        """Test search by vendor name"""
        response = client.get("/api/devices/search?q=apple")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) >= 1

    def test_search_case_insensitive(self, client):
        """Test that search is case insensitive"""
        response1 = client.get("/api/devices/search?q=apple")
        response2 = client.get("/api/devices/search?q=APPLE")
        response3 = client.get("/api/devices/search?q=Apple")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        data1 = response1.json()
        data2 = response2.json()
        data3 = response3.json()

        assert len(data1["devices"]) == len(data2["devices"]) == len(data3["devices"])

    def test_search_no_results(self, client):
        """Test search with no results"""
        response = client.get("/api/devices/search?q=nonexistent-device-xyz")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 0

    def test_search_with_status_filter_online(self, client):
        """Test search with online status filter"""
        response = client.get("/api/devices/search?q=192.168&status=online")
        assert response.status_code == 200
        data = response.json()
        assert data["status_filter"] == "online"
        # All test devices are online
        assert len(data["devices"]) >= 2

    def test_search_with_status_filter_offline(self, client):
        """Test search with offline status filter"""
        response = client.get("/api/devices/search?q=192.168&status=offline")
        assert response.status_code == 200
        data = response.json()
        assert data["status_filter"] == "offline"
        # No offline devices in test data
        assert len(data["devices"]) == 0

    def test_search_response_format(self, client):
        """Test that search response has correct format"""
        response = client.get("/api/devices/search?q=192.168.1.100")
        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "query" in data
        assert "status_filter" in data
        assert "devices" in data
        assert "total" in data
        assert "timestamp" in data

        # Check device structure
        if len(data["devices"]) > 0:
            device = data["devices"][0]
            assert "device_id" in device
            assert "mac_address" in device
            assert "current_ip" in device
            assert "status" in device
            assert "friendly_name" in device
            assert "vendor_name" in device
            assert "ip_history" in device

    def test_search_result_sorting(self, client):
        """Test that search results are sorted by last_seen"""
        response = client.get("/api/devices/search?q=192.168")
        assert response.status_code == 200
        data = response.json()

        devices = data["devices"]
        if len(devices) > 1:
            # Check that devices are sorted by last_seen descending
            for i in range(len(devices) - 1):
                assert devices[i]["last_seen"] >= devices[i + 1]["last_seen"]

    def test_search_special_characters(self, client):
        """Test search with special characters in query"""
        response = client.get("/api/devices/search?q=%3A")  # : character
        assert response.status_code == 200
        data = response.json()
        # Should handle gracefully
        assert "devices" in data

    def test_search_whitespace_handling(self, client):
        """Test that leading/trailing whitespace is handled"""
        response = client.get("/api/devices/search?q=%20%20raspberry%20%20")
        assert response.status_code == 200
        data = response.json()
        # Should still find devices despite whitespace
        assert len(data["devices"]) >= 1

    def test_search_max_results_performance(self, client):
        """Test search performance with multiple results"""
        import time

        start = time.time()
        response = client.get("/api/devices/search?q=192.168")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should complete in reasonable time
        assert elapsed < 1.0, f"Search took {elapsed:.2f}s, expected <1.0s"

    def test_search_timestamp_format(self, client):
        """Test that response timestamp is in ISO format"""
        response = client.get("/api/devices/search?q=192.168")
        assert response.status_code == 200
        data = response.json()

        # Check timestamp format
        timestamp = data["timestamp"]
        # Should be valid ISO 8601
        try:
            from datetime import datetime
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp}")

    def test_search_ip_history_included(self, client):
        """Test that IP history is included in results"""
        response = client.get("/api/devices/search?q=192.168.1.100")
        assert response.status_code == 200
        data = response.json()

        if len(data["devices"]) > 0:
            device = data["devices"][0]
            # Should have ip_history field
            assert "ip_history" in device
            # Should be a list
            assert isinstance(device["ip_history"], list)
