"""
Chester 5G Wireless Data Terminal API client for HomeSentinel.

Uses the custom /api endpoint with JSON-RPC style requests.
Password is base64-encoded before sending.
Authentication returns a session ID (sid) used in subsequent requests.
"""

import base64
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class ChesterAuthError(Exception):
    """Raised when Chester authentication fails."""


class ChesterAPIError(Exception):
    """Raised when Chester API requests fail."""


class ChesterClient:
    """Client for Chester 5G Wireless Data Terminal routers."""

    TOKEN_REFRESH_MARGIN = 60

    def __init__(
        self,
        host: str = "",
        username: str = "",
        password: str = "",
        port: int = 0,
        use_https: Optional[bool] = None,
        verify_ssl: bool = False,
        timeout: int = 10,
    ):
        env_host = os.getenv("CHESTER_HOST", "192.168.12.1")
        env_port = int(os.getenv("CHESTER_PORT", "80"))
        env_username = os.getenv("CHESTER_USERNAME", "admin")
        env_password = os.getenv("CHESTER_PASSWORD", "")
        env_use_https = os.getenv("CHESTER_USE_HTTPS", "false").lower() == "true"

        self.host = host or env_host
        self.username = username or env_username
        self.password = password or env_password
        self.port = port or env_port
        self.use_https = use_https if use_https is not None else env_use_https
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        self._session = requests.Session()
        self._session_id: Optional[str] = None
        self._session_expires_at: Optional[datetime] = None
        self._request_id: int = 0

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_https else "http"
        return f"{scheme}://{self.host}:{self.port}"

    def set_credentials(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 80,
        use_https: bool = False,
        verify_ssl: bool = False,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_https = use_https
        self.verify_ssl = verify_ssl
        self._session_id = None
        self._session_expires_at = None

    def _needs_login(self) -> bool:
        if not self._session_id or not self._session_expires_at:
            return True
        return datetime.utcnow() >= (self._session_expires_at - timedelta(seconds=self.TOKEN_REFRESH_MARGIN))

    def _next_mid(self) -> int:
        self._request_id += 1
        return self._request_id

    def authenticate(self) -> str:
        if not self.username or not self.password:
            raise ChesterAuthError("Missing Chester credentials")

        encoded_password = base64.b64encode(self.password.encode()).decode()

        payload = {
            "module": "login",
            "api": "login",
            "param": {
                "username": self.username,
                "password": encoded_password,
            },
        }

        try:
            resp = self._session.post(
                f"{self.base_url}/api",
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as e:
            raise ChesterAPIError(f"Connection failed: {e}") from e

        if resp.status_code != 200:
            raise ChesterAuthError(f"Authentication failed: HTTP {resp.status_code}")

        data = resp.json()
        errcode = data.get("errcode", -1)
        if errcode != 0:
            raise ChesterAuthError(f"Authentication failed: error code {errcode}")

        sid = data.get("sid")
        if not sid:
            raise ChesterAuthError("Authentication failed: no session ID returned")

        self._session_id = sid
        self._session_expires_at = datetime.utcnow() + timedelta(seconds=300)
        logger.info(f"Chester authenticated, session: {sid[:8]}...")
        return sid

    def _get_session_id(self) -> str:
        if self._needs_login():
            return self.authenticate()
        return self._session_id  # type: ignore[return-value]

    def api_call(self, module: str, api: str, param: Optional[Dict[str, Any]] = None) -> Any:
        sid = self._get_session_id()
        payload: Dict[str, Any] = {
            "module": module,
            "api": api,
            "sid": sid,
            "version": "1.0",
            "mid": self._next_mid(),
        }
        if param:
            payload["param"] = param

        try:
            resp = self._session.post(
                f"{self.base_url}/api",
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={
                    "Content-Type": "application/json",
                    "token": sid,
                },
            )
        except requests.RequestException as e:
            raise ChesterAPIError(f"Request failed: {e}") from e

        if resp.status_code != 200:
            raise ChesterAPIError(f"API call failed: HTTP {resp.status_code}")

        data = resp.json()
        errcode = data.get("errcode", -1)
        if errcode != 0 and errcode != 200:
            raise ChesterAPIError(f"API call failed: {module}.{api} error code {errcode}")

        return data.get("result", data)

    def test_connection(self) -> Dict[str, Any]:
        sid = self.authenticate()
        info = self.api_call("system", "get_info")
        return {
            "success": True,
            "session_id": sid,
            "board": info if isinstance(info, dict) else {"raw": info},
        }

    def get_board_info(self) -> Dict[str, Any]:
        return self.api_call("system", "get_info")

    def get_interfaces(self) -> Dict[str, Any]:
        return self.api_call("network", "get_wan")

    def get_wireless_status(self) -> Dict[str, Any]:
        return self.api_call("network", "get_wireless")

    def close(self):
        if self._session:
            self._session.close()
