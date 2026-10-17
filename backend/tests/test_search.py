"""
Tests for Device Search Service
"""

import pytest
import os
import sys
import tempfile
import uuid
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Database, NetworkDeviceRepository
from services.search_service import DeviceSearchService
from services.device_scanner import NetworkDeviceService


class TestDeviceSearchService:
    """Tests for device search functionality"""

    @pytest.fixture
    def temp_db(self):
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
    def device_repo(self, temp_db):
        """Create device repository"""
        return NetworkDeviceRepository(temp_db)

    @pytest.fixture
    def search_service(self, temp_db):
        """Create search service"""
        return DeviceSearchService(temp_db)

    @pytest.fixture
    def device_service(self, temp_db):
        """Create device service"""
        return NetworkDeviceService(temp_db)

    def setup_test_devices(self, device_repo):
        """Create test devices"""
        devices = []

        # Device 1: Raspberry Pi
        dev1 = device_repo.create_or_update(
            "device-1",
            "b8:27:eb:aa:bb:cc",
            "192.168.1.100"
        )
        device_repo.update_device_metadata(
            dev1['device_id'],
            friendly_name="Living Room Pi",
            vendor_name="Raspberry PI",
            device_type="single-board-computer"
        )
        devices.append(dev1)

        # Device 2: Router
        dev2 = device_repo.create_or_update(
            "device-2",
            "00:0c:29:aa:bb:dd",
            "192.168.1.1"
        )
        device_repo.update_device_metadata(
            dev2['device_id'],
            friendly_name="Network Router",
            vendor_name="CISCO",
            device_type="router"
        )
        devices.append(dev2)

        # Device 3: Phone
        dev3 = device_repo.create_or_update(
            "device-3",
            "aa:bb:cc:dd:ee:ff",
            "192.168.1.150"
        )
        device_repo.update_device_metadata(
            dev3['device_id'],
            friendly_name="John's Phone",
            vendor_name="APPLE",
            device_type="mobile"
        )
        devices.append(dev3)

        return devices

    def test_search_by_mac_prefix(self, device_repo, search_service):
        """Test searching by MAC address prefix"""
        self.setup_test_devices(device_repo)

        # Search for Raspberry Pi
        results = search_service.search_by_mac_prefix("b8:27")
        assert len(results) == 1
        assert results[0]['mac_address'] == "b8:27:eb:aa:bb:cc"

    def test_search_by_ip(self, device_repo, search_service):
        """Test searching by IP address"""
        self.setup_test_devices(device_repo)

        # Search for 192.168.1.1
        results = search_service.search_by_ip("192.168.1.1")
        assert len(results) >= 1
        assert any(r['current_ip'] == "192.168.1.1" for r in results)

    def test_search_by_ip_prefix(self, device_repo, search_service):
        """Test searching by IP prefix"""
        self.setup_test_devices(device_repo)

        # Search for 192.168.1.1
        results = search_service.search_by_ip("192.168.1")
        assert len(results) >= 2

    def test_search_by_friendly_name(self, device_repo, search_service):
        """Test searching by friendly name"""
        self.setup_test_devices(device_repo)

        # Search for raspberry
        results = search_service.search_by_friendly_name("raspberry")
        assert len(results) == 1
        assert results[0]['friendly_name'] == "Living Room Pi"

    def test_search_by_friendly_name_partial(self, device_repo, search_service):
        """Test searching by partial friendly name"""
        self.setup_test_devices(device_repo)

        # Search for "room"
        results = search_service.search_by_friendly_name("room")
        assert len(results) >= 1
        assert any("Room" in r.get('friendly_name', '') for r in results)

    def test_search_by_vendor(self, device_repo, search_service):
        """Test searching by vendor name"""
        self.setup_test_devices(device_repo)

        # Search for APPLE
        results = search_service.search_by_vendor("apple")
        assert len(results) == 1
        assert results[0]['vendor_name'] == "APPLE"

    def test_search_by_hostname(self, device_repo, search_service):
        """Test searching by hostname (empty by default)"""
        self.setup_test_devices(device_repo)

        # Should return no results since no hostnames set
        results = search_service.search_by_hostname("test-host")
        assert len(results) == 0

    def test_search_combined_query(self, device_repo, search_service):
        """Test that search queries work across all fields"""
        self.setup_test_devices(device_repo)

        # Search for "pi" - should match friendly name
        results = search_service.search("pi")
        assert len(results) >= 1
        assert any("pi" in r['friendly_name'].lower() for r in results)

        # Search for "apple" - should match vendor
        results = search_service.search("apple")
        assert len(results) >= 1
        assert any("apple" in r['vendor_name'].lower() for r in results)

    def test_search_with_status_filter(self, device_repo, search_service):
        """Test search with status filter"""
        self.setup_test_devices(device_repo)

        # All devices are online by default
        results = search_service.search("192.168", status_filter="online")
        assert len(results) >= 2

        # Search offline devices
        results = search_service.search("192.168", status_filter="offline")
        assert len(results) == 0

    def test_search_empty_query(self, search_service):
        """Test search with empty query"""
        results = search_service.search("")
        assert len(results) == 0

    def test_search_whitespace_query(self, search_service):
        """Test search with whitespace only query"""
        results = search_service.search("   ")
        assert len(results) == 0

    def test_search_no_results(self, device_repo, search_service):
        """Test search with no matching results"""
        self.setup_test_devices(device_repo)

        results = search_service.search("nonexistent-device")
        assert len(results) == 0

    def test_ip_history_tracking(self, device_repo, search_service):
        """Test that IP history is tracked when IP changes"""
        # Create a device
        device = device_repo.create_or_update(
            "device-history",
            "cc:dd:ee:ff:00:11",
            "192.168.1.200"
        )
        device_id = device['device_id']

        # Update IP
        search_service.update_ip_history(device_id, "192.168.1.201")

        # Check IP history
        history = search_service.get_device_ip_history(device_id)
        assert len(history) >= 1
        assert any(entry['ip'] == "192.168.1.200" for entry in history)

    def test_ip_history_no_change(self, device_repo, search_service):
        """Test that IP history is not updated when IP doesn't change"""
        # Create a device
        device = device_repo.create_or_update(
            "device-no-change",
            "cc:dd:ee:ff:00:22",
            "192.168.1.202"
        )
        device_id = device['device_id']

        # Try to update with same IP
        result = search_service.update_ip_history(device_id, "192.168.1.202")

        # Should return False (no update)
        assert result is False

    def test_ip_history_format(self, device_repo, search_service):
        """Test that IP history has correct format"""
        # Create a device
        device = device_repo.create_or_update(
            "device-format",
            "cc:dd:ee:ff:00:33",
            "192.168.1.203"
        )
        device_id = device['device_id']

        # Update IP
        search_service.update_ip_history(device_id, "192.168.1.204")

        # Get history
        history = search_service.get_device_ip_history(device_id)

        # Check format
        for entry in history:
            assert 'ip' in entry
            assert 'seen_at' in entry or 'current' in entry

    def test_search_result_enrichment(self, device_repo, search_service):
        """Test that search results include enriched IP history"""
        # Create a device
        device = device_repo.create_or_update(
            "device-enriched",
            "cc:dd:ee:ff:00:44",
            "192.168.1.205"
        )
        device_id = device['device_id']

        # Update IP to create history
        search_service.update_ip_history(device_id, "192.168.1.206")

        # Search and verify result
        results = search_service.search("192.168.1.206")
        assert len(results) == 1
        device_result = results[0]

        # Check that ip_history is parsed JSON
        assert isinstance(device_result.get('ip_history'), list)

    def test_case_insensitive_search(self, device_repo, search_service):
        """Test that search is case insensitive"""
        self.setup_test_devices(device_repo)

        # Search with different cases
        results_lower = search_service.search("apple")
        results_upper = search_service.search("APPLE")
        results_mixed = search_service.search("Apple")

        assert len(results_lower) > 0
        assert len(results_upper) > 0
        assert len(results_mixed) > 0
        assert len(results_lower) == len(results_upper) == len(results_mixed)

    def test_search_returns_sorted_results(self, device_repo, search_service):
        """Test that search results are sorted by last_seen"""
        devices = self.setup_test_devices(device_repo)

        # Search and check sorting
        results = search_service.search("192.168")
        assert len(results) > 0

        # Results should be sorted by last_seen descending
        for i in range(len(results) - 1):
            # Devices created later should appear first
            assert results[i]['last_seen'] >= results[i + 1]['last_seen']

    def test_search_performance(self, device_repo, search_service):
        """Test that search completes in reasonable time"""
        import time

        # Create many devices
        for i in range(50):
            device_repo.create_or_update(
                f"device-perf-{i}",
                f"aa:bb:cc:dd:ee:{i:02x}",
                f"192.168.1.{100 + i}"
            )

        # Time the search
        start = time.time()
        results = search_service.search("192.168.1")
        elapsed = time.time() - start

        # Should complete in less than 1 second
        assert elapsed < 1.0, f"Search took {elapsed:.2f}s, expected <1.0s"
        assert len(results) >= 50
