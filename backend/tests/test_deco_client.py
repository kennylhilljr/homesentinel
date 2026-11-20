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
import base64

from Crypto.PublicKey import RSA

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.deco_client as deco_client_module
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



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLOUD_ENV = {"DECO_USERNAME": "testuser@example.com", "DECO_PASSWORD": "testpass"}

# One real RSA key shared by every fake local router (generating keys is slow).
_RSA_KEY = RSA.generate(1024)
_RSA_NN = format(_RSA_KEY.n, "x")
_RSA_EE = format(_RSA_KEY.e, "x")


def _response(status_code=200, payload=None, headers=None):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = payload if payload is not None else {}
    resp.text = json.dumps(payload if payload is not None else {})
    resp.headers = headers or {}
    return resp


def _cloud_ok(result):
    """TP-Link cloud JSON-RPC success envelope."""
    return _response(200, {"error_code": 0, "result": result})


def _cloud_login(token):
    return _cloud_ok({"token": token})


def _b64(text):
    return base64.b64encode(text.encode()).decode()


class FakeLocalDeco:
    """Stands in for requests.Session.post against the Deco LuCI API on port 80.

    Answers the RSA key exchange, the AES-encrypted login, and AES-encrypted
    admin/* requests using the client's own DecoEncryption key/IV.
    """

    def __init__(self, client, stok="stok_abc123", sysauth="sysauth_xyz",
                 login_status=200, endpoints=None):
        self.client = client
        self.stok = stok
        self.sysauth = sysauth
        self.login_status = login_status
        self.endpoints = endpoints or {}
        self.requests = []  # (path, decrypted request dict)

    def _encrypted(self, payload, headers=None):
        data = self.client._encryption.aes_encrypt(json.dumps(payload))
        return _response(200, {"data": data}, headers)

    def __call__(self, url, **kwargs):
        if "login?form=keys" in url:
            return _response(200, {"result": {"password": [_RSA_NN, _RSA_EE]}})
        if "login?form=auth" in url:
            return _response(200, {"result": {"seq": 100, "key": [_RSA_NN, _RSA_EE]}})
        if "login?form=login" in url:
            if self.login_status != 200:
                return _response(self.login_status, {})
            return self._encrypted(
                {"error_code": 0, "result": {"stok": self.stok}},
                headers={"set-cookie": f"sysauth={self.sysauth}; path=/"},
            )
        prefix = f";stok={self.stok}/"
        assert prefix in url, f"unexpected URL {url}"
        assert kwargs.get("cookies") == {"sysauth": self.sysauth}
        path = url.split(prefix, 1)[1]
        request = json.loads(self.client._encryption.aes_decrypt(kwargs["data"]["data"]))
        self.requests.append((path, request))
        return self._encrypted({"error_code": 0, "result": self.endpoints.get(path, {})})


@pytest.fixture(autouse=True)
def _reset_client_list_state():
    """get_client_list keeps module-level 'endpoint broken' state; isolate tests."""
    with patch.object(deco_client_module, "_client_list_broken", False), \
            patch.object(deco_client_module, "_client_list_broken_time", None):
        yield


class TestDecoClientAuthentication:
    """Tests for authentication functionality"""

    @patch("services.deco_client.requests.Session.post")
    def test_successful_authentication(self, mock_post):
        """Cloud login: token is read from result.token of the JSON-RPC response"""
        mock_post.return_value = _cloud_login("test_token_12345")

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            token = client.authenticate()

            assert token == "test_token_12345"
            assert client._session_token == "test_token_12345"
            assert client._token_expiry is not None
            assert client.is_authenticated() is True

            payload = mock_post.call_args[1]["json"]
            assert payload["method"] == "login"
            assert payload["params"]["cloudUserName"] == "testuser@example.com"
            assert payload["params"]["cloudPassword"] == "testpass"

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_invalid_credentials(self, mock_post):
        """Cloud error -20601 means wrong account/password"""
        mock_post.return_value = _response(
            200, {"error_code": -20601, "msg": "Incorrect email or password"}
        )

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
        """Explicit credentials override env and are stored for re-authentication"""
        with patch("services.deco_client.requests.Session.post") as mock_post:
            mock_post.return_value = _cloud_login("explicit_token")

            with patch.dict(os.environ, {}, clear=True):
                client = DecoClient()
                token = client.authenticate(username="explicit_user", password="explicit_pass")

                assert token == "explicit_token"
                assert client.is_authenticated() is True
                assert client.username == "explicit_user"
                assert client.password == "explicit_pass"
                assert mock_post.call_args[1]["json"]["params"]["cloudUserName"] == "explicit_user"

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_no_token_in_response(self, mock_post):
        """Cloud login succeeding without a token is rejected"""
        mock_post.return_value = _cloud_ok({"accountId": "123"})  # Missing token

        with patch.dict(os.environ, CLOUD_ENV):
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
    def test_authentication_local_returns_stok_as_session_token(self, mock_post):
        """Local LuCI login: RSA/AES handshake yields stok + sysauth cookie"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            router = FakeLocalDeco(client, stok="stok_local_1", sysauth="cookie_1")
            mock_post.side_effect = router

            token = client.authenticate()

            assert token == "stok_local_1"
            assert client._session_token == "stok_local_1"
            assert client._sysauth == "cookie_1"
            assert client.username == "admin"  # local API always logs in as admin
            assert client.is_authenticated() is True

            urls = [c[0][0] for c in mock_post.call_args_list]
            assert urls == [
                f"{DecoClient.DEFAULT_LOCAL_ENDPOINT}/cgi-bin/luci/;stok=/login?form=keys",
                f"{DecoClient.DEFAULT_LOCAL_ENDPOINT}/cgi-bin/luci/;stok=/login?form=auth",
                f"{DecoClient.DEFAULT_LOCAL_ENDPOINT}/cgi-bin/luci/;stok=/login?form=login",
            ]
            # Login body is AES-encrypted and decrypts to the login operation
            login_body = mock_post.call_args_list[2][1]["data"]
            login_req = json.loads(client._encryption.aes_decrypt(login_body["data"]))
            assert login_req["operation"] == "login"
            assert login_req["params"]["password"] != "testpass"  # RSA-encrypted
            assert login_body["sign"]

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_local_rejected_raises_invalid_credentials(self, mock_post):
        """Local login HTTP 403 is reported as invalid credentials"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            mock_post.side_effect = FakeLocalDeco(client, login_status=403)

            with pytest.raises(InvalidCredentialsError, match="403"):
                client.authenticate()
            assert client.is_authenticated() is False

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_cloud_api_uses_verify_ssl_true(self, mock_post):
        """Cloud authentication always verifies TLS, even if verify_ssl=False is passed"""
        mock_post.return_value = _cloud_login("test_token")

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=True, verify_ssl=False)
            client.authenticate()

            assert mock_post.call_args[1]["verify"] is True

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_local_api_uses_verify_ssl_true_by_default(self, mock_post):
        """Every local login request uses verify=True by default"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            mock_post.side_effect = FakeLocalDeco(client)
            client.authenticate()

            assert mock_post.call_count == 3
            assert all(c[1]["verify"] is True for c in mock_post.call_args_list)

    @patch("services.deco_client.requests.Session.post")
    def test_authentication_local_api_uses_verify_ssl_false_when_disabled(self, mock_post):
        """Every local login request uses verify=False when explicitly disabled"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False, verify_ssl=False)
            mock_post.side_effect = FakeLocalDeco(client)
            client.authenticate()

            assert mock_post.call_count == 3
            assert all(c[1]["verify"] is False for c in mock_post.call_args_list)


class TestDecoClientSessionManagement:
    """Tests for session token management"""

    @patch("services.deco_client.requests.Session.post")
    def test_is_authenticated_true(self, mock_post):
        """Test is_authenticated returns True for valid session"""
        mock_post.return_value = _cloud_login("valid_token")

        with patch.dict(os.environ, CLOUD_ENV):
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
        mock_post.return_value = _cloud_login("expired_token")

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            client.authenticate()

            # Manually set expiry to past
            client._token_expiry = datetime.now() - timedelta(hours=1)

            assert client.is_authenticated() is False

    @patch("services.deco_client.requests.Session.post")
    def test_get_session_token_valid(self, mock_post):
        """get_session_token returns the cached token without re-authenticating"""
        mock_post.return_value = _cloud_login("valid_token")

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            client.authenticate()
            token = client.get_session_token()

            assert token == "valid_token"
            assert mock_post.call_count == 1

    @patch("services.deco_client.requests.Session.post")
    def test_get_session_token_refresh_on_expiry(self, mock_post):
        """get_session_token re-authenticates when the token is inside the refresh margin"""
        mock_post.side_effect = [_cloud_login("old_token"), _cloud_login("new_token")]

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            client.authenticate()

            # Token expires within TOKEN_REFRESH_MARGIN
            client._token_expiry = datetime.now() + timedelta(seconds=100)

            token = client.get_session_token()

            assert token == "new_token"
            assert mock_post.call_count == 2

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_no_token(self, mock_post):
        """Test _should_refresh_token returns True when no token"""
        with patch.dict(os.environ, {"DECO_USERNAME": "test", "DECO_PASSWORD": "pass"}):
            client = DecoClient()
            assert client._should_refresh_token() is True

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_approaching_expiry(self, mock_post):
        """Test _should_refresh_token returns True when token approaching expiry"""
        mock_post.return_value = _cloud_login("token")

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            client.authenticate()

            # Set token to expire within refresh margin
            client._token_expiry = datetime.now() + timedelta(seconds=200)

            assert client._should_refresh_token() is True

    @patch("services.deco_client.requests.Session.post")
    def test_should_refresh_token_valid(self, mock_post):
        """Test _should_refresh_token returns False for valid token"""
        mock_post.return_value = _cloud_login("token")

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            client.authenticate()

            # Set token to expire in far future
            client._token_expiry = datetime.now() + timedelta(hours=1)

            assert client._should_refresh_token() is False


class TestDecoClientAPIRequests:
    """Tests for API request methods"""

    def test_get_node_list(self):
        """Local get_node_list reads admin/device?form=device_list and decodes base64 names"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            with patch.object(DecoClient, "_local_encrypted_request") as mock_req:
                mock_req.return_value = {
                    "device_list": [
                        {"mac": "8C-90-2D-2D-9A-20", "name": _b64("Main Router"), "role": "master"},
                        {"mac": "8C-90-2D-2D-9A-21", "name": _b64("Satellite 1"), "role": "slave"},
                    ]
                }
                nodes = client.get_node_list()

            assert len(nodes) == 2
            assert nodes[0]["mac"] == "8C-90-2D-2D-9A-20"
            assert nodes[0]["name"] == "Main Router"
            assert nodes[1]["name"] == "Satellite 1"
            path, body = mock_req.call_args[0]
            assert path == "admin/device?form=device_list"
            assert json.loads(body) == {"operation": "read"}

    def test_get_client_list(self):
        """Local get_client_list reads all clients (device_mac=default) and decodes names"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            with patch.object(DecoClient, "_local_encrypted_request") as mock_req:
                mock_req.return_value = {
                    "client_list": [
                        {"mac": "AA-BB-CC-DD-EE-FF", "ip": "192.168.1.100", "name": _b64("Laptop")},
                        {"mac": "11-22-33-44-55-66", "ip": "192.168.1.101", "name": _b64("Phone")},
                    ]
                }
                clients = client.get_client_list()

            assert len(clients) == 2
            assert clients[0]["mac"] == "AA-BB-CC-DD-EE-FF"
            assert clients[0]["name"] == "Laptop"
            path, body = mock_req.call_args[0]
            assert path == "admin/client?form=client_list"
            assert json.loads(body) == {"operation": "read", "params": {"device_mac": "default"}}

    def test_get_client_list_endpoint_failure_returns_empty(self):
        """A failing local client_list endpoint yields [] instead of raising"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            with patch.object(
                DecoClient, "_local_encrypted_request",
                side_effect=APIConnectionError("HTTP 500"),
            ):
                assert client.get_client_list() == []

    def test_get_wifi_settings(self):
        """Local get_wifi_settings reads admin/wireless?form=wlan"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            with patch.object(DecoClient, "_local_encrypted_request") as mock_req:
                mock_req.return_value = {"ssid": "MyDeco", "band_steering": True}
                settings = client.get_wifi_settings()

            assert settings["ssid"] == "MyDeco"
            assert settings["band_steering"] is True
            path, body = mock_req.call_args[0]
            assert path == "admin/wireless?form=wlan"
            assert json.loads(body) == {"operation": "read"}

    @patch("services.deco_client.requests.Session.post")
    def test_api_request_invalid_credentials(self, mock_post):
        """Cloud request answered with 401 raises and clears the session token"""
        mock_post.side_effect = [_cloud_login("test_token"), _response(401, {})]

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            with pytest.raises(InvalidCredentialsError):
                client.get_node_list()
            assert client._session_token is None
            assert client.is_authenticated() is False

    @patch("services.deco_client.requests.Session.post")
    def test_api_request_connection_error(self, mock_post):
        """Cloud request connection failure is wrapped in APIConnectionError"""
        import requests

        mock_post.side_effect = [
            _cloud_login("test_token"),
            requests.exceptions.ConnectionError("Connection refused"),
        ]

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient()
            with pytest.raises(APIConnectionError, match="Failed to connect"):
                client.get_node_list()

    @patch("services.deco_client.requests.Session.post")
    def test_cloud_request_uses_verify_ssl_true(self, mock_post):
        """Cloud data requests (token in query string) use verify=True"""
        mock_post.side_effect = [_cloud_login("test_token"), _cloud_ok({"deviceList": []})]

        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=True)
            assert client.get_node_list() == []

            data_call = mock_post.call_args_list[1]
            assert data_call[0][0] == f"{DecoClient.DEFAULT_CLOUD_ENDPOINT}?token=test_token"
            assert data_call[1]["json"] == {"method": "getDeviceList"}
            assert data_call[1]["verify"] is True

    @patch("services.deco_client.requests.Session.post")
    def test_post_request_uses_verify_ssl_false_when_disabled(self, mock_post):
        """Local login and encrypted data requests all use verify=False when disabled"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False, verify_ssl=False)
            router = FakeLocalDeco(client, endpoints={
                "admin/wireless?form=wlan": {"ssid": "TestSSID"},
            })
            mock_post.side_effect = router

            settings = client.get_wifi_settings()  # authenticates on demand

            assert settings == {"ssid": "TestSSID"}
            assert router.requests == [("admin/wireless?form=wlan", {"operation": "read"})]
            assert mock_post.call_count == 4  # keys, auth, login, wlan
            assert all(c[1]["verify"] is False for c in mock_post.call_args_list)


class TestDecoClientContextManager:
    """Tests for context manager functionality"""

    @patch("services.deco_client.requests.Session.post")
    def test_context_manager_enter_exit(self, mock_post):
        """DecoClient works as a context manager and closes its HTTP session on exit"""
        mock_post.return_value = _cloud_login("test_token")

        with patch.dict(os.environ, CLOUD_ENV):
            with patch("services.deco_client.requests.Session.close") as mock_close:
                with DecoClient() as client:
                    assert client is not None
                    token = client.authenticate()
                    assert token == "test_token"
                mock_close.assert_called_once()

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
        mock_post.return_value = _cloud_login("test_token")

        with patch.dict(os.environ, CLOUD_ENV):
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

    @patch("services.deco_client.requests.Session.post")
    def test_complete_workflow_login_and_fetch_devices(self, mock_post):
        """Local LuCI workflow: RSA login, fetch nodes, fetch clients, logout on close"""
        with patch.dict(os.environ, CLOUD_ENV):
            client = DecoClient(use_cloud=False)
            router = FakeLocalDeco(client, stok="workflow_stok", endpoints={
                "admin/device?form=device_list": {
                    "device_list": [{"mac": "8C-90-2D-2D-9A-20", "name": _b64("Router"), "role": "master"}],
                },
                "admin/client?form=client_list": {
                    "client_list": [{"mac": "AA-BB-CC-DD-EE-FF", "name": _b64("Laptop"), "online": True}],
                },
            })
            mock_post.side_effect = router

            # Authenticate
            token = client.authenticate()
            assert token == "workflow_stok"

            # Fetch nodes
            nodes = client.get_node_list()
            assert len(nodes) == 1
            assert nodes[0]["name"] == "Router"

            # Fetch clients
            clients = client.get_client_list()
            assert len(clients) == 1
            assert clients[0]["mac"] == "AA-BB-CC-DD-EE-FF"
            assert clients[0]["name"] == "Laptop"

            # Close logs out of the local session
            client.close()
            assert client.is_authenticated() is False

            assert router.requests == [
                ("admin/device?form=device_list", {"operation": "read"}),
                ("admin/client?form=client_list",
                 {"operation": "read", "params": {"device_mac": "default"}}),
                ("admin/system?form=logout", {"operation": "logout"}),
            ]
