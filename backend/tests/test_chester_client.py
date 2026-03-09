"""Tests for Chester OpenWrt client."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chester_client import ChesterClient, ChesterAuthError, ChesterAPIError


class TestChesterClient:
    def test_base_url_http(self):
        client = ChesterClient(host="192.168.8.1", port=8080, use_https=False)
        assert client.base_url == "http://192.168.8.1:8080"

    def test_base_url_https(self):
        client = ChesterClient(host="router.local", port=443, use_https=True)
        assert client.base_url == "https://router.local:443"

    @patch("services.chester_client.requests.Session.post")
    def test_authenticate_success(self, mock_post):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "result": [0, {"ubus_rpc_session": "abc123", "expires": 300}],
        }
        mock_post.return_value = mock_resp

        client = ChesterClient(password="secret")
        sid = client.authenticate()
        assert sid == "abc123"

    @patch("services.chester_client.requests.Session.post")
    def test_authenticate_missing_credentials(self, _mock_post):
        client = ChesterClient(password="")
        with pytest.raises(ChesterAuthError):
            client.authenticate()

    @patch("services.chester_client.requests.Session.post")
    def test_ubus_call_success(self, mock_post):
        login_resp = Mock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "result": [0, {"ubus_rpc_session": "abc123", "expires": 300}],
        }

        call_resp = Mock()
        call_resp.status_code = 200
        call_resp.json.return_value = {
            "result": [0, {"hostname": "chester"}],
        }

        mock_post.side_effect = [login_resp, call_resp]

        client = ChesterClient(password="secret")
        result = client.ubus_call("system", "board")
        assert result["hostname"] == "chester"

    @patch("services.chester_client.requests.Session.post")
    def test_ubus_call_error_code(self, mock_post):
        login_resp = Mock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "result": [0, {"ubus_rpc_session": "abc123", "expires": 300}],
        }

        call_resp = Mock()
        call_resp.status_code = 200
        call_resp.json.return_value = {
            "result": [1, {}],
        }

        mock_post.side_effect = [login_resp, call_resp]

        client = ChesterClient(password="secret")
        with pytest.raises(ChesterAPIError):
            client.ubus_call("system", "board")
