#!/usr/bin/env python3
"""
Test runner for DecoClient without pytest dependency issues
Uses unittest instead
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.deco_client import (
    DecoClient,
    InvalidCredentialsError,
    SessionExpiredError,
    APIConnectionError,
)


class TestDecoClientInitialization(unittest.TestCase):
    """Tests for DecoClient initialization"""

    def test_init_default_cloud_endpoint(self):
        """Test initialization with default cloud endpoint"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=True)
            self.assertTrue(client.use_cloud)
            self.assertEqual(client.active_endpoint, DecoClient.DEFAULT_CLOUD_ENDPOINT)

    def test_init_default_local_endpoint(self):
        """Test initialization with default local endpoint"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            client = DecoClient(use_cloud=False)
            self.assertFalse(client.use_cloud)
            self.assertEqual(client.active_endpoint, DecoClient.DEFAULT_LOCAL_ENDPOINT)

    def test_init_custom_endpoints(self):
        """Test initialization with custom endpoints"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test@user.com", "DECO_PASSWORD": "pass"}):
            cloud_url = "https://custom.cloud.com"
            local_url = "http://custom.local.com:9000"
            client = DecoClient(cloud_endpoint=cloud_url, local_endpoint=local_url, use_cloud=True)
            self.assertEqual(client.cloud_endpoint, cloud_url)
            self.assertEqual(client.local_endpoint, local_url)
            self.assertEqual(client.active_endpoint, cloud_url)

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
            self.assertEqual(client.username, "testuser@example.com")
            self.assertEqual(client.password, "secretpassword")


class TestDecoClientAuthentication(unittest.TestCase):
    """Tests for authentication functionality"""

    @patch("services.deco_client.requests.Session.post")
    def test_successful_authentication(self, mock_post):
        """Test successful authentication"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token_12345"}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            token = client.authenticate()

            self.assertEqual(token, "test_token_12345")
            self.assertEqual(client._session_token, "test_token_12345")
            self.assertTrue(client.is_authenticated())

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_invalid_credentials(self, mock_post):
        """Test authentication with invalid credentials"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "wrong@example.com", "DECO_PASSWORD": "wrongpass"},
        ):
            client = DecoClient()
            with self.assertRaises(InvalidCredentialsError):
                client.authenticate()

    def test_authentication_missing_credentials(self):
        """Test authentication without credentials"""
        with patch.dict(os.environ, {}, clear=True):
            client = DecoClient()
            with self.assertRaises(InvalidCredentialsError):
                client.authenticate()

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_explicit_credentials(self, mock_post):
        """Test authentication with explicit credentials"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "explicit_token"}
        mock_post.return_value = mock_response

        client = DecoClient()
        token = client.authenticate(username="explicit_user", password="explicit_pass")

        self.assertEqual(token, "explicit_token")
        self.assertTrue(client.is_authenticated())

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_no_token_in_response(self, mock_post):
        """Test authentication when response has no token"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with self.assertRaises(InvalidCredentialsError):
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
            with self.assertRaises(APIConnectionError):
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
            with self.assertRaises(APIConnectionError):
                client.authenticate()


class TestDecoClientSessionManagement(unittest.TestCase):
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
            self.assertTrue(client.is_authenticated())

    def test_is_authenticated_false_no_token(self):
        """Test is_authenticated returns False when no token exists"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test", "DECO_PASSWORD": "pass"}):
            client = DecoClient()
            self.assertFalse(client.is_authenticated())

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

            client._token_expiry = datetime.now() - timedelta(hours=1)

            self.assertFalse(client.is_authenticated())

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_no_token(self, mock_post):
        """Test _should_refresh_token returns True when no token"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test", "DECO_PASSWORD": "pass"}):
            client = DecoClient()
            self.assertTrue(client._should_refresh_token())

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

            client._token_expiry = datetime.now() + timedelta(seconds=200)

            self.assertTrue(client._should_refresh_token())

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

            client._token_expiry = datetime.now() + timedelta(hours=1)

            self.assertFalse(client._should_refresh_token())


class TestDecoClientAPIRequests(unittest.TestCase):
    """Tests for API request methods"""

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_node_list(self, mock_post, mock_get):
        """Test get_node_list API call"""
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

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

            self.assertEqual(len(nodes), 2)
            self.assertEqual(nodes[0]["id"], "node1")

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_client_list(self, mock_post, mock_get):
        """Test get_client_list API call"""
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

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

            self.assertEqual(len(clients), 2)
            self.assertEqual(clients[0]["mac"], "AA:BB:CC:DD:EE:FF")

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_get_wifi_settings(self, mock_post, mock_get):
        """Test get_wifi_settings API call"""
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

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

            self.assertEqual(settings["ssid"], "MyDeco")
            self.assertTrue(settings["band_steering"])

    @patch("services.deco_client.requests.Session.put")
    @patch("services.deco_client.requests.Session.post")
    def test_update_wifi_settings(self, mock_post, mock_put):
        """Test update_wifi_settings API call"""
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        mock_put_response = Mock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"success": True}
        mock_put.return_value = mock_put_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            response = client.update_wifi_settings(ssid="NewSSID", band_steering=False)

            self.assertTrue(response["success"])

    @patch("services.deco_client.requests.Session.get")
    @patch("services.deco_client.requests.Session.post")
    def test_api_request_invalid_credentials(self, mock_post, mock_get):
        """Test API request when session is invalid (401)"""
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        mock_get_response = Mock()
        mock_get_response.status_code = 401
        mock_get_response.text = "Unauthorized"
        mock_get.return_value = mock_get_response

        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient()
            with self.assertRaises(InvalidCredentialsError):
                client.get_node_list()


class TestDecoClientContextManager(unittest.TestCase):
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
                self.assertIsNotNone(client)
                token = client.authenticate()
                self.assertEqual(token, "test_token")

    @patch("services.deco_client.requests.Session.post")
    def test_repr(self, mock_post):
        """Test string representation"""
        with patch.dict(
            os.environ,
            {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"},
        ):
            client = DecoClient(use_cloud=True)
            repr_str = repr(client)

            self.assertIn("DecoClient", repr_str)
            self.assertIn("cloud", repr_str)
            self.assertIn("not authenticated", repr_str)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
