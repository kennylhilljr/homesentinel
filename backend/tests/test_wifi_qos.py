"""
Tests for WiFi Config and QoS API endpoints
Tests for /api/deco/wifi-config and /api/deco/qos endpoints
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.deco_service import DecoService
from services.deco_client import InvalidCredentialsError, APIConnectionError


class TestWiFiConfigService:
    """Tests for WiFi config retrieval from DecoService"""

    def test_get_wifi_config_returns_dictionary(self):
        """Test get_wifi_config returns a dictionary"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "MyNetwork",
            "bands": ["2.4 GHz", "5 GHz"],
            "channel": "Auto",
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert isinstance(config, dict)
        assert "ssid" in config
        assert "bands" in config

    def test_get_wifi_config_includes_ssid(self):
        """Test SSID is properly extracted and included"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "channel": "Auto",
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert config["ssid"] == "TestNetwork"

    def test_get_wifi_config_extracts_bands(self):
        """Test bands are properly extracted"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_2_4ghz_enabled": True,
            "band_5ghz_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert "2.4 GHz" in config["bands"]
        assert "5 GHz" in config["bands"]

    def test_get_wifi_config_extracts_channel_info(self):
        """Test channel information is extracted"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "channel_2_4ghz": "6",
            "channel_5ghz": "36",
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert config["channel_2_4ghz"] == "6"
        assert config["channel_5ghz"] == "36"

    def test_get_wifi_config_includes_band_steering(self):
        """Test band steering status is included"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert config["band_steering_enabled"] is True

    def test_get_wifi_config_caches_results(self):
        """Test WiFi config results are cached"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
        }

        service = DecoService(deco_client=mock_client)

        # First call
        config1 = service.get_wifi_config()
        # Second call should use cache
        config2 = service.get_wifi_config()

        assert config1 == config2
        # Verify API was only called once
        assert mock_client.get_wifi_settings.call_count == 1

    def test_get_wifi_config_expires_cache(self):
        """Test WiFi config cache expires after TTL"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
        }

        service = DecoService(deco_client=mock_client)
        service.CACHE_TTL = 1  # Set TTL to 1 second for testing

        # First call
        config1 = service.get_wifi_config()

        # Simulate cache expiry
        import time
        time.sleep(1.1)

        # Second call should fetch fresh data
        config2 = service.get_wifi_config()

        # Verify API was called twice
        assert mock_client.get_wifi_settings.call_count == 2

    def test_get_wifi_config_handles_api_error(self):
        """Test error handling for API failures"""
        mock_client = Mock()
        mock_client.get_wifi_settings.side_effect = APIConnectionError("API unavailable")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.get_wifi_config()

    def test_get_wifi_config_handles_auth_error(self):
        """Test error handling for authentication failures"""
        mock_client = Mock()
        mock_client.get_wifi_settings.side_effect = InvalidCredentialsError("Invalid credentials")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(InvalidCredentialsError):
            service.get_wifi_config()

    def test_get_wifi_config_includes_timestamp(self):
        """Test that last_updated timestamp is included"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
        }

        service = DecoService(deco_client=mock_client)
        config = service.get_wifi_config()

        assert "last_updated" in config
        # Verify it's a valid timestamp string
        datetime.fromisoformat(config["last_updated"])


class TestQoSService:
    """Tests for QoS settings retrieval from DecoService"""

    def test_get_qos_settings_returns_dictionary(self):
        """Test get_qos_settings returns a dictionary"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        assert isinstance(qos, dict)
        assert "qos_enabled" in qos
        assert "devices" in qos

    def test_get_qos_settings_includes_devices(self):
        """Test devices are included in QoS settings"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
                "priority": "Normal",
                "connectionType": "WiFi",
            },
            {
                "name": "Device2",
                "macAddress": "00:11:22:33:44:66",
                "priority": "High",
                "connectionType": "Wired",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        assert len(qos["devices"]) == 2
        assert qos["total_devices"] == 2

    def test_get_qos_settings_device_has_required_fields(self):
        """Test QoS device entries have all required fields"""
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
        assert "device_name" in device
        assert "mac_address" in device
        assert "priority" in device
        assert "connection_type" in device
        assert "ip_address" in device

    def test_get_qos_settings_caches_results(self):
        """Test QoS settings are cached"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "name": "Device1",
                "macAddress": "00:11:22:33:44:55",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # First call
        qos1 = service.get_qos_settings()
        # Second call should use cache
        qos2 = service.get_qos_settings()

        assert qos1 == qos2
        # Verify API was only called once
        assert mock_client.get_client_list.call_count == 1

    def test_get_qos_settings_handles_empty_clients(self):
        """Test handling of no connected clients"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = []

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        assert qos["qos_enabled"] is True
        assert len(qos["devices"]) == 0
        assert qos["total_devices"] == 0

    def test_get_qos_settings_handles_api_error(self):
        """Test error handling for API failures"""
        mock_client = Mock()
        mock_client.get_client_list.side_effect = APIConnectionError("API unavailable")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.get_qos_settings()

    def test_get_qos_settings_handles_auth_error(self):
        """Test error handling for authentication failures"""
        mock_client = Mock()
        mock_client.get_client_list.side_effect = InvalidCredentialsError("Invalid credentials")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(InvalidCredentialsError):
            service.get_qos_settings()

    def test_get_qos_settings_includes_timestamp(self):
        """Test that last_updated timestamp is included"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = []

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        assert "last_updated" in qos
        # Verify it's a valid timestamp string
        datetime.fromisoformat(qos["last_updated"])

    def test_get_qos_settings_prioritizes_fields(self):
        """Test that device fields are properly mapped from various API response formats"""
        mock_client = Mock()
        mock_client.get_client_list.return_value = [
            {
                "clientName": "OldFormatDevice",
                "mac_address": "00:11:22:33:44:77",
                "priority": "Low",
                "type": "Wired",
                "ip_address": "192.168.1.200",
            }
        ]

        service = DecoService(deco_client=mock_client)
        qos = service.get_qos_settings()

        device = qos["devices"][0]
        assert device["device_name"] == "OldFormatDevice"
        assert device["mac_address"] == "00:11:22:33:44:77"
        assert device["priority"] == "Low"
        assert device["connection_type"] == "Wired"


class TestCacheClearing:
    """Tests for cache clearing functionality"""

    def test_clear_cache_clears_all_caches(self):
        """Test that clear_cache clears all cached data"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {"ssid": "Network"}
        mock_client.get_client_list.return_value = []

        service = DecoService(deco_client=mock_client)

        # Populate all caches
        service.get_wifi_config()
        service.get_qos_settings()

        # Verify caches are populated
        assert service._wifi_config_cache is not None
        assert service._qos_cache is not None

        # Clear cache
        service.clear_cache()

        # Verify all caches are cleared
        assert service._wifi_config_cache is None
        assert service._qos_cache is None
        assert service._nodes_cache is None

    def test_clear_cache_forces_fresh_fetch(self):
        """Test that clearing cache forces fresh API fetch"""
        mock_client = Mock()
        mock_client.get_wifi_settings.return_value = {"ssid": "Network"}

        service = DecoService(deco_client=mock_client)

        # First fetch
        service.get_wifi_config()
        # Clear cache
        service.clear_cache()
        # Second fetch should hit API again
        service.get_wifi_config()

        # Verify API was called twice
        assert mock_client.get_wifi_settings.call_count == 2
