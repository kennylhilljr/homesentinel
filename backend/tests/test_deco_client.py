"""
Tests for Deco API Client
Tests authentication, session management, and API requests with mocking
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.deco_client import (
    DecoClient,
    InvalidCredentialsError,
    SessionExpiredError,
    APIConnectionError,
)


class TestDecoClientInitialization:
    """Tests for DecoClient initialization"""

    def test_init_default_cloud_endpoint(self):
        """Test initialization with default cloud endpoint"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=True)
            assert client.use_cloud is True
            assert client.active_endpoint == DecoClient.DEFAULT_CLOUD_ENDPOINT
            assert client.cloud_endpoint == DecoClient.DEFAULT_CLOUD_ENDPOINT

    def test_init_default_local_endpoint(self):
        """Test initialization with default local endpoint"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=False)
            assert client.use_cloud is False
            assert client.active_endpoint == DecoClient.DEFAULT_LOCAL_ENDPOINT
            assert client.local_endpoint == DecoClient.DEFAULT_LOCAL_ENDPOINT

    def test_init_custom_endpoints(self):
        """Test initialization with custom endpoints"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            cloud_url = "https://custom.cloud.com"
            local_url = "http://custom.local.com:9000"
            client = DecoClient(cloud_endpoint=cloud_url, local_endpoint=local_url, use_cloud=True)
            assert client.cloud_endpoint == cloud_url
            assert client.local_endpoint == local_url
            assert client.active_endpoint == cloud_url

    def test_init_loads_credentials_from_env(self):
        """Test that credentials are loaded from environment variables"""
        with patch.dict(
            os.environ,
            {
                "DECO_USERNAME": "testuser@example.com",
                "DECO_PASSWORD": "secretpassword",
            },
        ):
            client = DecoClient()
            assert client.username == "testuser@example.com"
            assert client.password == "secretpassword"

    def test_init_no_credentials_in_env(self):
        """Test initialization without credentials in environment"""
        with patch.dict(os.environ, {}, clear=True):
            client = DecoClient()
            assert client.username == ""
            assert client.password == ""

    def test_init_cloud_api_always_verifies_ssl(self):
        """Test that cloud API always forces SSL verification"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            # Cloud API should always have verify_ssl=True, regardless of parameter
            client = DecoClient(use_cloud=True, verify_ssl=False)
            assert client.verify_ssl is True

    def test_init_cloud_api_verify_ssl_default(self):
        """Test that cloud API defaults to SSL verification"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=True)
            assert client.verify_ssl is True

    def test_init_local_api_default_verify_ssl_enabled(self):
        """Test that local API defaults to SSL verification enabled"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=False)
            assert client.verify_ssl is True

    def test_init_local_api_verify_ssl_can_be_disabled(self):
        """Test that local API allows SSL verification to be disabled"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=False, verify_ssl=False)
            assert client.verify_ssl is False

    def test_init_local_api_verify_ssl_can_be_enabled(self):
        """Test that local API allows SSL verification to be explicitly enabled"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=False, verify_ssl=True)
            assert client.verify_ssl is True


class TestDecoClientAuthentication:
    """Tests for authentication functionality"""

    @patch("services.deco_client.requests.Session.post")
    def test_successful_authentication(self, mock_post):
        """Test successful authentication"""
        # Mock successful auth response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token_12345", "expires_in": 3600}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            token = client.authenticate()

            assert token == "test_token_12345"
            assert client._session_token == "test_token_12345"
            assert client._token_expiry is not None
            assert client.is_authenticated() is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_invalid_credentials(self, mock_post):
        """Test authentication with invalid credentials"""
        # Mock 401 unauthorized response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "wrong@example.com", "DECO_PASSWORD": "wrongpass"},
        ):
            client = DecoClient()
            with pytest.raises(InvalidCredentialsError, match="Invalid TP-Link credentials"):
                client.authenticate()

    def test_authentication_missing_credentials(self):
        """Test authentication without credentials"""
        with patch.dict(os.environ, {}, clear=True):
            client = DecoClient()
            with pytest.raises(InvalidCredentialsError, match="not provided"):
                client.authenticate()

    def test_authentication_explicit_credentials(self):
        """Test authentication with explicit credentials"""
        with patch("services.deco_client.requests.Session.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"token": "explicit_token"}
            mock_post.return_value = mock_response

            client = DecoClient()
            token = client.authenticate(username="explicit_user", password="explicit_pass")

            assert token == "explicit_token"
            assert client.is_authenticated() is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_no_token_in_response(self, mock_post):
        """Test authentication when response has no token"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}  # Missing token
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with pytest.raises(InvalidCredentialsError, match="no token in response"):
                client.authenticate()

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_connection_error(self, mock_post):
        """Test authentication with connection error"""
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with pytest.raises(APIConnectionError, match="Failed to connect"):
                client.authenticate()

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_timeout(self, mock_post):
        """Test authentication with timeout"""
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with pytest.raises(APIConnectionError, match="timed out"):
                client.authenticate()

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_with_session_token_key(self, mock_post):
        """Test authentication when token is returned as 'sessionToken'"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sessionToken": "session_token_value"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            token = client.authenticate()

            assert token == "session_token_value"
            assert client.is_authenticated() is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_with_access_token_key(self, mock_post):
        """Test authentication when token is returned as 'access_token'"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "access_token_value"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            token = client.authenticate()

            assert token == "access_token_value"
            assert client.is_authenticated() is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_cloud_api_uses_verify_ssl_true(self, mock_post):
        """Test that cloud API authentication always uses verify_ssl=True"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=True)
            client.authenticate()

            # Verify that post was called with verify=True
            call_args = mock_post.call_args
            assert call_args[1]["verify"] is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_local_api_uses_verify_ssl_true_by_default(self, mock_post):
        """Test that local API authentication uses verify_ssl=True by default"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=False)
            client.authenticate()

            # Verify that post was called with verify=True
            call_args = mock_post.call_args
            assert call_args[1]["verify"] is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_local_api_uses_verify_ssl_false_when_disabled(self, mock_post):
        """Test that local API authentication uses verify_ssl=False when explicitly disabled"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=False, verify_ssl=False)
            client.authenticate()

            # Verify that post was called with verify=False
            call_args = mock_post.call_args
            assert call_args[1]["verify"] is False


class TestDecoClientSessionManagement:
    """Tests for session token management"""

    @patch("services.deco_client.requests.Session.post")
    def test_is_authenticated_true(self, mock_post):
        """Test is_authenticated returns True for valid session"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "valid_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            client.authenticate()
            assert client.is_authenticated() is True

    def test_is_authenticated_false_no_token(self):
        """Test is_authenticated returns False when no token exists"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test", "DECO_PASSWORD": "pass"}):
            client = DecoClient()
            assert client.is_authenticated() is False

    @patch("services.deco_client.requests.Session.post")
    def test_is_authenticated_false_expired_token(self, mock_post):
        """Test is_authenticated returns False for expired token"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "expired_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            client.authenticate()

            # Manually set expiry to past
            client._token_expiry = datetime.now() - timedelta(hours=1)

            assert client.is_authenticated() is False

    @patch("services.deco_client.requests.Session.post")
    def test_get_session_token_valid(self, mock_post):
        """Test get_session_token returns token when valid"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "valid_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            client.authenticate()
            token = client.get_session_token()

            assert token == "valid_token"

    @patch("services.deco_client.requests.Session.post")
    def test_get_session_token_refresh_on_expiry(self, mock_post):
        """Test get_session_token refreshes token when approaching expiry"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "new_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            client.authenticate()

            # Manually set token to expire soon (within refresh margin)
            client._token_expiry = datetime.now() + timedelta(seconds=100)

            # Mock should be called again for refresh
            token = client.get_session_token()

            # Verify post was called more than once (initial + refresh)
            assert mock_post.call_count >= 1

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_no_token(self, mock_post):
        """Test _should_refresh_token returns True when no token"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test", "DECO_PASSWORD": "pass"}):
            client = DecoClient()
            assert client._should_refresh_token() is True

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_approaching_expiry(self, mock_post):
        """Test _should_refresh_token returns True when token approaching expiry"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            client.authenticate()

            # Set token to expire within refresh margin
            client._token_expiry = datetime.now() + timedelta(seconds=200)

            assert client._should_refresh_token() is True

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_valid(self, mock_post):
        """Test _should_refresh_token returns False for valid token"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            client.authenticate()

            # Set token to expire in far future
            client._token_expiry = datetime.now() + timedelta(hours=1)

            assert client._should_refresh_token() is False


class TestDecoClientAPIRequests:
    """Tests for API request methods"""

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_node_list(self, mock_post, mock_get):
        """Test get_node_list API call"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock node list response
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "nodes": [
                {"id": "node1", "name": "Main Router"},
                {"id": "node2", "name": "Satellite 1"},
            ]
        }
        mock_get.return_value = mock_get_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            nodes = client.get_node_list()

            assert len(nodes) == 2
            assert nodes[0]["id"] == "node1"
            assert nodes[1]["name"] == "Satellite 1"

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_client_list(self, mock_post, mock_get):
        """Test get_client_list API call"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock client list response
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "clients": [
                {"mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.100"},
                {"mac": "11:22:33:44:55:66", "ip": "192.168.1.101"},
            ]
        }
        mock_get.return_value = mock_get_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            clients = client.get_client_list()

            assert len(clients) == 2
            assert clients[0]["mac"] == "AA:BB:CC:DD:EE:FF"

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_wifi_settings(self, mock_post, mock_get):
        """Test get_wifi_settings API call"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock WiFi settings response
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "ssid": "MyDeco",
            "password": "secure_password",
            "band_steering": True,
        }
        mock_get.return_value = mock_get_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            settings = client.get_wifi_settings()

            assert settings["ssid"] == "MyDeco"
            assert settings["band_steering"] is True

    @patch("services.deco_client.requests.Session.put")
    @patch("services.deco_client.requests.Session.post")
    def test_update_wifi_settings(self, mock_post, mock_put):
        """Test update_wifi_settings API call"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock update response
        mock_put_response = Mock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"success": True, "message": "WiFi settings updated"}
        mock_put.return_value = mock_put_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            response = client.update_wifi_settings(ssid="NewSSID", band_steering=False)

            assert response["success"] is True
            # Verify that PUT was called with correct data
            call_args = mock_put.call_args
            assert call_args[1]["json"]["ssid"] == "NewSSID"
            assert call_args[1]["json"]["band_steering"] is False

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_api_request_invalid_credentials(self, mock_post, mock_get):
        """Test API request when session is invalid (401)"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock API response with 401 Unauthorized
        mock_get_response = Mock()
        mock_get_response.status_code = 401
        mock_get_response.text = "Unauthorized"
        mock_get.return_value = mock_get_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with pytest.raises(InvalidCredentialsError):
                client.get_node_list()

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_api_request_connection_error(self, mock_post, mock_get):
        """Test API request with connection error"""
        import requests

        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock GET with connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with pytest.raises(APIConnectionError, match="Failed to connect"):
                client.get_node_list()

    @patch("services.deco_client.requests.Session.post")
    def test_update_wifi_no_settings(self, mock_post):
        """Test update_wifi_settings with no settings provided"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            response = client.update_wifi_settings()

            assert "No settings to update" in response.get("message", "")

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_request_uses_verify_ssl_true(self, mock_post, mock_get):
        """Test that GET requests use verify_ssl parameter (cloud API with verify=True)"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock GET response
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"nodes": []}
        mock_get.return_value = mock_get_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=True)  # Cloud API with verify=True
            client.get_node_list()

            # Verify GET was called with verify=True
            call_args = mock_get.call_args
            assert call_args[1]["verify"] is True

    @patch("services.deco_client.requests.Session.put")
    @patch("services.deco_client.requests.Session.post")
    def test_post_request_uses_verify_ssl_false_when_disabled(self, mock_post, mock_put):
        """Test that POST requests use verify_ssl parameter (local API with verify=False)"""
        # Mock authentication response
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock update response (PUT request)
        mock_update_response = Mock()
        mock_update_response.status_code = 200
        mock_update_response.json.return_value = {"success": True}
        mock_put.return_value = mock_update_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=False, verify_ssl=False)  # Local API with verify=False
            client.update_wifi_settings(ssid="TestSSID")

            # Check that auth POST was called with verify=False
            auth_call = mock_post.call_args
            assert auth_call[1]["verify"] is False

            # Check that PUT was called with verify=False
            put_call = mock_put.call_args
            assert put_call[1]["verify"] is False

    @patch("services.deco_client.requests.Session.put")
    @patch("services.deco_client.requests.Session.post")
    def test_put_request_uses_verify_ssl_setting(self, mock_post, mock_put):
        """Test that PUT requests use verify_ssl parameter"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock PUT response
        mock_put_response = Mock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"success": True}
        mock_put.return_value = mock_put_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=False, verify_ssl=False)
            client.update_wifi_settings(ssid="NewSSID")

            # Verify PUT was called with verify=False
            call_args = mock_put.call_args
            assert call_args[1]["verify"] is False

    @patch("services.deco_client.requests.Session.delete")
    @patch("services.deco_client.requests.Session.post")
    def test_delete_request_uses_verify_ssl_setting(self, mock_post, mock_delete):
        """Test that DELETE requests use verify_ssl parameter"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        # Mock DELETE response
        mock_delete_response = Mock()
        mock_delete_response.status_code = 200
        mock_delete_response.json.return_value = {"success": True}
        mock_delete.return_value = mock_delete_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=False, verify_ssl=True)
            # Make a DELETE request through _make_request
            client._make_request("DELETE", "/api/test")

            # Verify DELETE was called with verify=True
            call_args = mock_delete.call_args
            assert call_args[1]["verify"] is True


class TestDecoClientContextManager:
    """Tests for context manager functionality"""

    @patch("services.deco_client.requests.Session.post")
    def test_context_manager_enter_exit(self, mock_post):
        """Test DecoClient as context manager"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            with DecoClient() as client:
                assert client is not None
                token = client.authenticate()
                assert token == "test_token"

    @patch("services.deco_client.requests.Session.post")
    def test_repr(self, mock_post):
        """Test string representation"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=True)
            repr_str = repr(client)

            assert "DecoClient" in repr_str
            assert "cloud" in repr_str
            assert "not authenticated" in repr_str


class TestDecoClientErrorHandling:
    """Tests for error handling and edge cases"""

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_server_error(self, mock_post):
        """Test authentication with 500 server error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with pytest.raises(APIConnectionError):
                client.authenticate()

    @patch("services.deco_client.requests.Session.post")
    def test_token_expiry_tracking(self, mock_post):
        """Test that token expiry is properly tracked"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            before_auth = datetime.now()
            client.authenticate()
            after_auth = datetime.now()

            assert client._token_expiry is not None
            expected_min = before_auth + timedelta(seconds=client.SESSION_TIMEOUT)
            expected_max = after_auth + timedelta(seconds=client.SESSION_TIMEOUT)

            assert expected_min <= client._token_expiry <= expected_max


class TestDecoClientIntegration:
    """Integration tests for complete workflows"""

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_complete_workflow_login_and_fetch_devices(self, mock_post, mock_get):
        """Test complete workflow: login, fetch nodes, fetch clients"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "workflow_token"}

        # Mock node list
        mock_nodes_response = Mock()
        mock_nodes_response.status_code = 200
        mock_nodes_response.json.return_value = {
            "nodes": [{"id": "node1", "name": "Router"}]
        }

        # Mock client list
        mock_clients_response = Mock()
        mock_clients_response.status_code = 200
        mock_clients_response.json.return_value = {
            "clients": [{"mac": "AA:BB:CC:DD:EE:FF"}]
        }

        # Set up side effects
        mock_post.return_value = mock_auth_response
        mock_get.side_effect = [mock_nodes_response, mock_clients_response]

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()

            # Authenticate
            token = client.authenticate()
            assert token == "workflow_token"

            # Fetch nodes
            nodes = client.get_node_list()
            assert len(nodes) == 1

            # Fetch clients
            clients = client.get_client_list()
            assert len(clients) == 1
