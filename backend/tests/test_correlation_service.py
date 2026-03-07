"""
Tests for Correlation Service
Tests Deco client correlation with LAN devices by MAC address
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.correlation_service import CorrelationService
from services.deco_service import DecoService


class TestCorrelationServiceInitialization:
    """Tests for CorrelationService initialization"""

    def test_init_accepts_services(self):
        """Test initialization with DecoService and device repository"""
        mock_deco_service = Mock(spec=DecoService)
        mock_device_repo = Mock()

        service = CorrelationService(mock_deco_service, mock_device_repo)

        assert service.deco_service is mock_deco_service
        assert service.device_repo is mock_device_repo


class TestMacNormalization:
    """Tests for MAC address normalization"""

    def test_normalize_mac_lowercase_colons(self):
        """Test normalization of MAC with colons"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address("00:11:22:33:44:55")
        assert result == "00:11:22:33:44:55"

    def test_normalize_mac_uppercase_colons(self):
        """Test normalization of uppercase MAC with colons"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address("AA:BB:CC:DD:EE:FF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_mac_dashes(self):
        """Test normalization of MAC with dashes"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address("AA-BB-CC-DD-EE-FF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_mac_no_separators(self):
        """Test normalization of MAC without separators"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address("AABBCCDDEEFF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_mac_mixed_case(self):
        """Test normalization of mixed case MAC"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address("Aa:Bb:Cc:Dd:Ee:Ff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_mac_empty(self):
        """Test normalization of empty MAC"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address("")
        assert result == ""

    def test_normalize_mac_none(self):
        """Test normalization of None MAC"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        result = service.normalize_mac_address(None)
        assert result == ""


class TestCorrelationByMac:
    """Tests for MAC-based correlation logic"""

    def test_correlate_matching_clients_and_devices(self):
        """Test correlation of matching Deco clients and LAN devices"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_clients = [
            {
                "macAddress": "00:11:22:33:44:55",
                "clientName": "iPhone",
            }
        ]

        lan_devices = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",
                "current_ip": "192.168.1.50",
                "vendor_name": "APPLE",
                "friendly_name": "john-iphone",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
            deco_clients, lan_devices
        )

        assert len(merged) == 1
        assert merged[0]["device_id"] == "device1"
        assert merged[0]["deco_client_name"] == "iPhone"
        assert merged[0]["current_ip"] == "192.168.1.50"
        assert len(unmatched_deco) == 0
        assert len(unmatched_lan) == 0

    def test_correlate_with_mac_format_variations(self):
        """Test correlation works with different MAC formats"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_clients = [
            {
                "macAddress": "00-11-22-33-44-55",  # Dashes
                "clientName": "Laptop",
            }
        ]

        lan_devices = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",  # Colons
                "current_ip": "192.168.1.100",
                "vendor_name": "DELL",
                "friendly_name": "work-laptop",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
            deco_clients, lan_devices
        )

        assert len(merged) == 1
        assert merged[0]["deco_client_name"] == "Laptop"

    def test_correlate_unmatched_deco_clients(self):
        """Test unmatched Deco clients are identified"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_clients = [
            {
                "macAddress": "00:11:22:33:44:55",
                "clientName": "iPhone",
            },
            {
                "macAddress": "AA:BB:CC:DD:EE:FF",
                "clientName": "iPad",
            }
        ]

        lan_devices = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",
                "current_ip": "192.168.1.50",
                "vendor_name": "APPLE",
                "friendly_name": "john-iphone",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
            deco_clients, lan_devices
        )

        assert len(merged) == 1
        assert len(unmatched_deco) == 1
        assert unmatched_deco[0]["clientName"] == "iPad"

    def test_correlate_unmatched_lan_devices(self):
        """Test unmatched LAN devices are identified"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_clients = [
            {
                "macAddress": "00:11:22:33:44:55",
                "clientName": "iPhone",
            }
        ]

        lan_devices = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",
                "current_ip": "192.168.1.50",
                "vendor_name": "APPLE",
                "friendly_name": "john-iphone",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            },
            {
                "device_id": "device2",
                "mac_address": "11:22:33:44:55:66",
                "current_ip": "192.168.1.100",
                "vendor_name": "UNKNOWN",
                "friendly_name": "",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
            deco_clients, lan_devices
        )

        assert len(merged) == 1
        assert len(unmatched_deco) == 0
        assert len(unmatched_lan) == 1

    def test_correlate_multiple_devices(self):
        """Test correlation with 5+ devices"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        # Create 6 Deco clients
        deco_clients = [
            {"macAddress": f"00:11:22:33:44:{i:02x}", "clientName": f"Device{i}"}
            for i in range(6)
        ]

        # Create 5 matching LAN devices
        lan_devices = [
            {
                "device_id": f"device{i}",
                "mac_address": f"00:11:22:33:44:{i:02x}",
                "current_ip": f"192.168.1.{50+i}",
                "vendor_name": "VENDOR",
                "friendly_name": f"device-{i}",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
            for i in range(5)
        ]

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
            deco_clients, lan_devices
        )

        assert len(merged) == 5
        assert len(unmatched_deco) == 1
        assert len(unmatched_lan) == 0

    def test_correlate_empty_lists(self):
        """Test correlation with empty lists"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac([], [])

        assert len(merged) == 0
        assert len(unmatched_deco) == 0
        assert len(unmatched_lan) == 0

    def test_correlate_clients_missing_mac(self):
        """Test correlation ignores clients without MAC address"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_clients = [
            {
                "clientName": "Device1",
                # Missing macAddress
            }
        ]

        lan_devices = []

        merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
            deco_clients, lan_devices
        )

        assert len(merged) == 0


class TestMergeDeviceData:
    """Tests for merging device data"""

    def test_merge_includes_all_fields(self):
        """Test merged device includes all required fields"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_client = {
            "clientName": "iPhone",
            "macAddress": "00:11:22:33:44:55",
        }

        lan_device = {
            "device_id": "device1",
            "mac_address": "00:11:22:33:44:55",
            "current_ip": "192.168.1.50",
            "vendor_name": "APPLE",
            "friendly_name": "john-iphone",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }

        merged = service._merge_device_data(deco_client, lan_device)

        assert merged["device_id"] == "device1"
        assert merged["mac_address"] == "00:11:22:33:44:55"
        assert merged["current_ip"] == "192.168.1.50"
        assert merged["deco_client_name"] == "iPhone"
        assert merged["vendor_name"] == "APPLE"
        assert merged["friendly_name"] == "john-iphone"
        assert merged["status"] == "online"

    def test_merge_handles_missing_deco_fields(self):
        """Test merged device handles missing Deco fields"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        service = CorrelationService(mock_deco_service, mock_device_repo)

        deco_client = {
            "macAddress": "00:11:22:33:44:55",
            # Missing clientName
        }

        lan_device = {
            "device_id": "device1",
            "mac_address": "00:11:22:33:44:55",
            "current_ip": "192.168.1.50",
            "vendor_name": "UNKNOWN",
            "friendly_name": "",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }

        merged = service._merge_device_data(deco_client, lan_device)

        assert merged["deco_client_name"] == "Unknown"


class TestGetMergedClients:
    """Tests for get_merged_clients method"""

    def test_get_merged_clients_success(self):
        """Test successful retrieval of merged clients"""
        mock_deco_service = Mock()
        mock_deco_client = Mock()
        mock_deco_client.get_client_list.return_value = [
            {
                "macAddress": "00:11:22:33:44:55",
                "clientName": "iPhone",
            }
        ]
        mock_deco_service.deco_client = mock_deco_client

        mock_device_repo = Mock()
        mock_device_repo.list_all.return_value = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",
                "current_ip": "192.168.1.50",
                "vendor_name": "APPLE",
                "friendly_name": "john-iphone",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]

        service = CorrelationService(mock_deco_service, mock_device_repo)
        result = service.get_merged_clients()

        assert result["total_merged"] == 1
        assert len(result["merged_devices"]) == 1
        assert result["unmatched_deco_count"] == 0
        assert result["unmatched_lan_devices"] == 0
        assert "correlation_stats" in result
        assert result["correlation_stats"]["correlation_percentage"] == 100.0

    def test_get_merged_clients_includes_stats(self):
        """Test that merged clients response includes correlation stats"""
        mock_deco_service = Mock()
        mock_deco_client = Mock()
        mock_deco_client.get_client_list.return_value = [
            {"macAddress": "00:11:22:33:44:55", "clientName": "Device1"},
            {"macAddress": "AA:BB:CC:DD:EE:FF", "clientName": "Device2"},
        ]
        mock_deco_service.deco_client = mock_deco_client

        mock_device_repo = Mock()
        mock_device_repo.list_all.return_value = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",
                "current_ip": "192.168.1.50",
                "vendor_name": "VENDOR1",
                "friendly_name": "device1",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]

        service = CorrelationService(mock_deco_service, mock_device_repo)
        result = service.get_merged_clients()

        assert "correlation_stats" in result
        stats = result["correlation_stats"]
        assert stats["total_deco_clients"] == 2
        assert stats["total_lan_devices"] == 1
        assert stats["total_merged"] == 1
        assert stats["correlation_percentage"] == 50.0

    def test_get_merged_clients_includes_timestamp(self):
        """Test that response includes timestamp"""
        mock_deco_service = Mock()
        mock_deco_client = Mock()
        mock_deco_client.get_client_list.return_value = []
        mock_deco_service.deco_client = mock_deco_client

        mock_device_repo = Mock()
        mock_device_repo.list_all.return_value = []

        service = CorrelationService(mock_deco_service, mock_device_repo)
        result = service.get_merged_clients()

        assert "timestamp" in result
        # Verify it's a valid ISO format timestamp
        timestamp = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
        assert timestamp is not None

    def test_get_merged_clients_error_handling(self):
        """Test error handling in get_merged_clients"""
        mock_deco_service = Mock()
        mock_deco_client = Mock()
        mock_deco_client.get_client_list.side_effect = Exception("API Error")
        mock_deco_service.deco_client = mock_deco_client

        mock_device_repo = Mock()

        service = CorrelationService(mock_deco_service, mock_device_repo)

        with pytest.raises(Exception):
            service.get_merged_clients()


class TestGetDecoClients:
    """Tests for get_deco_clients method"""

    def test_get_deco_clients_success(self):
        """Test successful retrieval of Deco clients"""
        mock_deco_service = Mock()
        mock_deco_client = Mock()
        clients = [
            {"macAddress": "00:11:22:33:44:55", "clientName": "Device1"}
        ]
        mock_deco_client.get_client_list.return_value = clients
        mock_deco_service.deco_client = mock_deco_client

        service = CorrelationService(mock_deco_service, Mock())
        result = service.get_deco_clients()

        assert result == clients
        mock_deco_client.get_client_list.assert_called_once()


class TestGetLanDevices:
    """Tests for get_lan_devices method"""

    def test_get_lan_devices_success(self):
        """Test successful retrieval of LAN devices"""
        mock_deco_service = Mock()
        mock_device_repo = Mock()
        devices = [
            {
                "device_id": "device1",
                "mac_address": "00:11:22:33:44:55",
                "current_ip": "192.168.1.50",
                "vendor_name": "VENDOR",
                "friendly_name": "device1",
                "status": "online",
                "first_seen": "2026-03-01T10:00:00Z",
                "last_seen": "2026-03-07T02:23:00Z",
            }
        ]
        mock_device_repo.list_all.return_value = devices

        service = CorrelationService(mock_deco_service, mock_device_repo)
        result = service.get_lan_devices()

        assert result == devices
        mock_device_repo.list_all.assert_called_once()
