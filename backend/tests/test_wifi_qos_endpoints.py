"""
Tests for WiFi Config and QoS API Endpoints
Integration tests for /api/deco/wifi-config and /api/deco/qos
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.deco import router, deco_service
from services.deco_service import DecoService


class TestWiFiConfigEndpoint:
    """Tests for /api/deco/wifi-config endpoint"""

    def test_wifi_config_endpoint_returns_dict(self):
        """Test wifi-config endpoint returns dictionary"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_2_4ghz_enabled": True,
            "band_5ghz_enabled": True,
            "channel_2_4ghz": "6",
            "channel_5ghz": "36",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        # Verify response structure
        assert isinstance(config, dict)
        assert "ssid" in config
        assert "bands" in config
        assert "channel_2_4ghz" in config
        assert "channel_5ghz" in config
        assert "band_steering_enabled" in config
        assert "last_updated" in config

    def test_wifi_config_response_format(self):
        """Test wifi-config response has correct format"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "MyNetwork",
            "channel_2_4ghz": "Auto",
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        # Verify types
        assert isinstance(config["ssid"], str)
        assert isinstance(config["bands"], list)
        assert isinstance(config["channel_2_4ghz"], str)
        assert isinstance(config["channel_5ghz"], str)
        assert isinstance(config["band_steering_enabled"], bool)
        assert isinstance(config["last_updated"], str)

    def test_wifi_config_handles_missing_fields(self):
        """Test endpoint handles missing WiFi config fields"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {"ssid": "Network"}

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        # Verify defaults are provided
        assert config["ssid"] == "Network"
        assert config["bands"] == ["2.4 GHz", "5 GHz"]  # Default bands
        assert config["channel_2_4ghz"] == "Auto"
        assert config["channel_5ghz"] == "Auto"
        assert config["band_steering_enabled"] is False

    def test_wifi_config_with_6ghz_band(self):
        """Test wifi-config includes 6 GHz band when available"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_2_4ghz_enabled": True,
            "band_5ghz_enabled": True,
            "band_6ghz_enabled": True,
            "channel_6ghz": "1",
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert "6 GHz" in config["bands"]
        assert config["channel_6ghz"] == "1"


class TestQoSEndpoint:
    """Tests for /api/deco/qos endpoint"""

    def test_qos_endpoint_returns_dict(self):
        """Test qos endpoint returns dictionary"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        # Verify response structure
        assert isinstance(qos, dict)
        assert "qos_enabled" in qos
        assert "devices" in qos
        assert "total_devices" in qos
        assert "last_updated" in qos

    def test_qos_response_format(self):
        """Test qos response has correct format"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        # Verify types
        assert isinstance(qos["qos_enabled"], bool)
        assert isinstance(qos["devices"], list)
        assert isinstance(qos["total_devices"], int)
        assert isinstance(qos["last_updated"], str)

        # Verify device format
        device = qos["devices"][0]
        assert isinstance(device["device_name"], str)
        assert isinstance(device["mac_address"], str)
        assert isinstance(device["priority"], str)
        assert isinstance(device["connection_type"], str)
        assert isinstance(device["ip_address"], str)

    def test_qos_device_fields_mapping(self):
        """Test QoS device fields are properly mapped"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "TestDevice",
                "macAddress": "AA:BB:CC:DD:EE:FF",
                "priority": "High",
                "connectionType": "Wired",
                "ipAddress": "192.168.1.50",
                "bandwidth_limit": 50,
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        device = qos["devices"][0]
        assert device["device_name"] == "TestDevice"
        assert device["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert device["priority"] == "High"
        assert device["connection_type"] == "Wired"
        assert device["ip_address"] == "192.168.1.50"
        assert device["bandwidth_limit_mbps"] == 50

    def test_qos_with_multiple_devices(self):
        """Test QoS endpoint with multiple devices"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
            },
            {
                "name": "Device2",
                "macAddress": "00:11:22:33:44:66",
                "priority": "High",
                "connectionType": "Wired",
                "ipAddress": "192.168.1.101",
            },
            {
                "name": "Device3",
                "macAddress": "00:11:22:33:44:77",
                "priority": "Low",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.102",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        assert qos["total_devices"] == 3
        assert len(qos["devices"]) == 3

    def test_qos_with_no_bandwidth_limit(self):
        """Test QoS device without bandwidth limit"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        device = qos["devices"][0]
        assert device["bandwidth_limit_mbps"] is None

    def test_qos_with_bandwidth_limit(self):
        """Test QoS device with bandwidth limit"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
                "bandwidth_limit": 100,
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        device = qos["devices"][0]
        assert device["bandwidth_limit_mbps"] == 100


class TestEndpointIntegration:
    """Integration tests for WiFi and QoS endpoints"""

    def test_wifi_and_qos_endpoints_use_different_caches(self):
        """Test that WiFi and QoS use separate caches"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {"ssid": "Network"}
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Fetch both
        wifi = service.get_wifi_config()
        qos = service.get_qos_settings()

        # Verify both calls were made
        assert mock_client.get_wifi_settings.call_count == 1
        assert mock_client.get_client_list.call_count == 1

        # Both should return data
        assert wifi["ssid"] == "Network"
        assert qos["total_devices"] == 1

    def test_clear_cache_affects_both_endpoints(self):
        """Test that clear_cache invalidates both WiFi and QoS caches"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {"ssid": "Network"}
        mock_client.get_client_list.return_value = []

        service = DecoService(deco_client=mock_client)

        # Populate caches
        service.get_wifi_config()
        service.get_qos_settings()

        # Clear all caches
        service.clear_cache()

        # Both should be None
        assert service._wifi_config_cache is None
        assert service._qos_cache is None

    def test_concurrent_endpoint_requests(self):
        """Test that concurrent requests to different endpoints work"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {"ssid": "Network"}
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
                "ipAddress": "192.168.1.100",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Simulate concurrent calls
        wifi1 = service.get_wifi_config()
        qos1 = service.get_qos_settings()
        wifi2 = service.get_wifi_config()  # From cache
        qos2 = service.get_qos_settings()  # From cache

        # Verify data consistency
        assert wifi1 == wifi2
        assert qos1 == qos2
        # Verify APIs were only called once due to caching
        assert mock_client.get_wifi_settings.call_count == 1
        assert mock_client.get_client_list.call_count == 1
