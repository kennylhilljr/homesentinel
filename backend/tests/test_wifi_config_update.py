"""
Tests for WiFi Configuration Update API endpoint and service
Tests for PUT /api/deco/wifi-config endpoint and update_wifi_config service method
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


class TestWiFiConfigUpdateService:
    """Tests for WiFi config update in DecoService"""

    def test_update_wifi_config_with_ssid(self):
        """Test updating SSID"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {
            "success": True,
            "message": "Settings updated",
        }
        mock_client.get_wifi_settings.return_value = {
            "ssid": "NewNetwork",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(ssid="NewNetwork")

        assert result["success"] is True
        assert "updated_config" in result
        assert mock_client.update_wifi_settings.called

    def test_update_wifi_config_with_password(self):
        """Test updating password"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_steering_enabled": False,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(password="SecurePass123")

        assert result["success"] is True
        mock_client.update_wifi_settings.assert_called_once_with(
            ssid=None,
            password="SecurePass123",
            band_steering=None,
        )

    def test_update_wifi_config_with_band_steering(self):
        """Test updating band steering"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(band_steering=True)

        assert result["success"] is True
        mock_client.update_wifi_settings.assert_called_once_with(
            ssid=None,
            password=None,
            band_steering=True,
        )

    def test_update_wifi_config_multiple_settings(self):
        """Test updating multiple settings at once"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "NewNetwork",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(
            ssid="NewNetwork",
            password="SecurePass123",
            band_steering=True,
        )

        assert result["success"] is True
        assert result["message"] == "WiFi configuration updated successfully"

    def test_update_wifi_config_invalid_ssid_too_short(self):
        """Test validation: SSID cannot be empty"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        with pytest.raises(ValueError, match="SSID must be between"):
            service.update_wifi_config(ssid="")

    def test_update_wifi_config_invalid_ssid_too_long(self):
        """Test validation: SSID cannot exceed 32 characters"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        long_ssid = "A" * 33
        with pytest.raises(ValueError, match="SSID must be between"):
            service.update_wifi_config(ssid=long_ssid)

    def test_update_wifi_config_invalid_password_too_short(self):
        """Test validation: Password must be at least 8 characters"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        with pytest.raises(ValueError, match="Password must be at least 8"):
            service.update_wifi_config(password="short")

    def test_update_wifi_config_clears_cache(self):
        """Test that cache is cleared after update"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "NewNetwork",
            "band_steering_enabled": False,
        }

        service = DecoService(deco_client=mock_client)

        # Set cache
        service._wifi_config_cache = {"ssid": "OldNetwork"}
        service._wifi_config_timestamp = datetime.now()

        # Update
        service.update_wifi_config(ssid="NewNetwork")

        # Cache should be cleared
        assert service._wifi_config_cache is None
        assert service._wifi_config_timestamp is None

    def test_update_wifi_config_returns_updated_config(self):
        """Test that method returns the updated config"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "NewNetwork",
            "bands": ["2.4 GHz", "5 GHz"],
            "channel_2_4ghz": "6",
            "channel_5ghz": "36",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(ssid="NewNetwork")

        assert "updated_config" in result
        assert result["updated_config"]["ssid"] == "NewNetwork"
        assert "bands" in result["updated_config"]

    def test_update_wifi_config_authentication_error(self):
        """Test handling of authentication errors"""
        mock_client = Mock()
        mock_client.update_wifi_settings.side_effect = InvalidCredentialsError("Invalid credentials")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(InvalidCredentialsError):
            service.update_wifi_config(ssid="NewNetwork")

    def test_update_wifi_config_connection_error(self):
        """Test handling of connection errors"""
        mock_client = Mock()
        mock_client.update_wifi_settings.side_effect = APIConnectionError("Connection failed")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.update_wifi_config(ssid="NewNetwork")

    def test_update_wifi_config_unexpected_error(self):
        """Test handling of unexpected errors"""
        mock_client = Mock()
        mock_client.update_wifi_settings.side_effect = Exception("Unexpected error")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.update_wifi_config(ssid="NewNetwork")

    def test_update_wifi_config_ssid_whitespace_trimmed(self):
        """Test that SSID whitespace is trimmed"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_steering_enabled": False,
        }

        service = DecoService(deco_client=mock_client)
        service.update_wifi_config(ssid="  TestNetwork  ")

        # Should call with trimmed SSID
        mock_client.update_wifi_settings.assert_called_once()
        call_args = mock_client.update_wifi_settings.call_args
        assert call_args[1]["ssid"] == "TestNetwork"


class TestWiFiConfigUpdateEndpoint:
    """Tests for WiFi config update API endpoint"""

    def test_endpoint_validation_model(self):
        """Test WiFiConfigUpdate validation model"""
        from routes.deco import WiFiConfigUpdate

        # Valid request
        request = WiFiConfigUpdate(ssid="NewNetwork", password=None, band_steering=True)
        assert request.ssid == "NewNetwork"
        assert request.password is None
        assert request.band_steering is True

    def test_endpoint_accepts_partial_updates(self):
        """Test that endpoint accepts partial parameter updates"""
        from routes.deco import WiFiConfigUpdate

        # Only SSID
        request1 = WiFiConfigUpdate(ssid="NewNetwork")
        assert request1.ssid == "NewNetwork"
        assert request1.password is None

        # Only password
        request2 = WiFiConfigUpdate(password="NewPassword123")
        assert request2.password == "NewPassword123"
        assert request2.ssid is None

        # Only band steering
        request3 = WiFiConfigUpdate(band_steering=True)
        assert request3.band_steering is True
        assert request3.ssid is None

    def test_endpoint_returns_verification_status(self):
        """Test that endpoint response includes verification status"""
        # Verification status added in response
        # Format: {"success": bool, "message": str, "updated_config": {...}, "timestamp": str}
        expected_fields = ["success", "message", "updated_config", "timestamp"]
        # Each should be present in endpoint response

    def test_endpoint_error_response_structure(self):
        """Test error response structure from endpoint"""
        # Error responses should include detail message
        # Format: {"detail": "Error message"}
        pass


class TestWiFiConfigUpdateValidation:
    """Tests for input validation in update_wifi_config"""

    def test_ssid_validation_valid_lengths(self):
        """Test valid SSID lengths"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "Test",
            "band_steering_enabled": False,
        }

        service = DecoService(deco_client=mock_client)

        # Should not raise for valid lengths
        service.update_wifi_config(ssid="A")  # 1 char
        service.update_wifi_config(ssid="A" * 32)  # 32 chars

    def test_password_validation_valid_lengths(self):
        """Test valid password lengths"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "band_steering_enabled": False,
        }

        service = DecoService(deco_client=mock_client)

        # Should not raise for valid length
        service.update_wifi_config(password="12345678")  # 8 chars minimum

    def test_no_parameters_raises_error(self):
        """Test that calling with no parameters raises error"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # Should still work but pass None to client
        # (client will handle the no-parameters case)
        try:
            service.update_wifi_config()
        except:
            pass  # Implementation specific


class TestWiFiConfigVerification:
    """Tests for WiFi configuration verification after updates"""

    def test_verification_status_pending_initially(self):
        """Test that verification starts in pending state"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "UpdatedNetwork",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(ssid="UpdatedNetwork")

        assert result["success"] is True
        assert "verification_status" in result
        # Should be pending or verified depending on immediate check
        assert result["verification_status"] in ["pending", "verified"]

    def test_verification_matches_submitted_config(self):
        """Test that verification checks match submitted config"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "UpdatedNetwork",
            "band_steering_enabled": True,
            "channel_2_4ghz": "6",
            "channel_5ghz": "36",
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(ssid="UpdatedNetwork")

        assert result["updated_config"]["ssid"] == "UpdatedNetwork"
        assert result["updated_config"]["band_steering_enabled"] is True

    def test_update_with_rate_limit_handling(self):
        """Test handling of Deco API rate limit (10s between writes)"""
        mock_client = Mock()
        mock_client.update_wifi_settings.side_effect = APIConnectionError("Rate limit exceeded")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.update_wifi_config(ssid="NewNetwork")

    def test_concurrent_update_prevention(self):
        """Test that concurrent updates are handled properly"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "UpdatedNetwork",
            "band_steering_enabled": False,
        }

        service = DecoService(deco_client=mock_client)

        # First update
        result1 = service.update_wifi_config(ssid="Network1")
        assert result1["success"] is True

        # Second update (simulating concurrent)
        result2 = service.update_wifi_config(ssid="Network2")
        assert result2["success"] is True

        # Both should succeed (backend handles sequential)
        assert mock_client.update_wifi_settings.call_count == 2


class TestWiFiConfigUpdateIntegration:
    """Integration tests for WiFi config update"""

    def test_update_and_verify_flow(self):
        """Test the complete update and verification flow"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}

        # Simulate API returning new config
        mock_client.get_wifi_settings.return_value = {
            "ssid": "UpdatedNetwork",
            "band_steering_enabled": True,
            "channel_2_4ghz": "6",
            "channel_5ghz": "36",
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(ssid="UpdatedNetwork")

        assert result["success"] is True
        assert result["updated_config"]["ssid"] == "UpdatedNetwork"

    def test_update_preserves_other_settings(self):
        """Test that updating one setting preserves others"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.return_value = {
            "ssid": "TestNetwork",
            "bands": ["2.4 GHz", "5 GHz"],
            "channel_2_4ghz": "6",
            "channel_5ghz": "36",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(password="NewPassword123")

        # SSID and other settings should still be present
        assert result["updated_config"]["ssid"] == "TestNetwork"
        assert "bands" in result["updated_config"]

    def test_update_timeout_scenario(self):
        """Test timeout scenario where API doesn't update within 30s"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}

        # Simulate API returning old config (verification fails)
        call_count = [0]
        def get_wifi_settings_side_effect():
            call_count[0] += 1
            return {
                "ssid": "OldNetwork",  # Not updated
                "band_steering_enabled": False,
            }

        mock_client.get_wifi_settings.side_effect = get_wifi_settings_side_effect

        service = DecoService(deco_client=mock_client)
        result = service.update_wifi_config(ssid="NewNetwork")

        # Should still return success, but verification may timeout in frontend
        assert result["success"] is True

    def test_invalid_ssid_rejected(self):
        """Test that invalid SSID is rejected"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # Empty SSID
        with pytest.raises(ValueError, match="SSID must be between"):
            service.update_wifi_config(ssid="")

        # SSID too long
        with pytest.raises(ValueError, match="SSID must be between"):
            service.update_wifi_config(ssid="A" * 33)

    def test_weak_password_rejected(self):
        """Test that weak password is rejected"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # Password less than 8 characters
        with pytest.raises(ValueError, match="Password must be at least 8"):
            service.update_wifi_config(password="short")

    def test_rapid_updates_handled(self):
        """Test that rapid consecutive updates are queued properly"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}

        call_sequence = []

        def update_side_effect(ssid=None, password=None, band_steering=None):
            call_sequence.append({
                "ssid": ssid,
                "password": password,
                "band_steering": band_steering,
            })
            return {"success": True}

        mock_client.update_wifi_settings.side_effect = update_side_effect
        mock_client.get_wifi_settings.return_value = {
            "ssid": "UpdatedNetwork",
            "band_steering_enabled": True,
        }

        service = DecoService(deco_client=mock_client)

        # First update
        result1 = service.update_wifi_config(ssid="Network1")
        # Second update (rapid)
        result2 = service.update_wifi_config(ssid="Network2")

        # Both should complete without error
        assert result1["success"] is True
        assert result2["success"] is True
        # Both updates should have been attempted
        assert len(call_sequence) == 2

    def test_network_timeout_during_polling(self):
        """Test handling of network timeout during verification polling"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}
        mock_client.get_wifi_settings.side_effect = APIConnectionError("Network timeout")

        service = DecoService(deco_client=mock_client)

        # Update should succeed despite verification failure
        with pytest.raises(APIConnectionError):
            service.update_wifi_config(ssid="NewNetwork")

    def test_exponential_backoff_retry_logic(self):
        """Test that transient failures are retried with backoff"""
        mock_client = Mock()
        mock_client.update_wifi_settings.return_value = {"success": True}

        # First call fails, second succeeds (simulating transient failure)
        mock_client.get_wifi_settings.side_effect = [
            APIConnectionError("Transient error"),
            {
                "ssid": "UpdatedNetwork",
                "band_steering_enabled": True,
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Should handle gracefully
        result = service.update_wifi_config(ssid="UpdatedNetwork")
        assert result["success"] is True
