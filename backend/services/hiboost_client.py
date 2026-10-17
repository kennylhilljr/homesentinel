"""
HiBoost Signal Booster API client for HomeSentinel.

Communicates with the HiBoost Signal Supervisor cloud API.
Authentication uses SHA-256 hashed password + RSA encrypted password.
The API returns device parameters as hex-encoded OID values.
"""

import base64
import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key

logger = logging.getLogger(__name__)

# HiBoost cloud RSA public key (from Signal Supervisor APK)
RSA_PUBLIC_KEY_B64 = (
    "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAOi4JZRPhx/VqrzOWLhYxy7lVckMPDCN"
    "+pH3r4QRu+NYeIKULOkIpyBZtUb6RhwxlUu6S2CEOcA9k2EdYpaess0CAwEAAQ=="
)

# Default cloud server
DEFAULT_API_URL = "https://www.signalsupervisor.com/iot-service"

# Band definitions with OID mappings
BANDS = [
    {
        "name": "LTE700",
        "prefix": "04",
        "freq_uplink": "698-716MHz",
        "freq_downlink": "728-746MHz",
    },
    {
        "name": "CELL800",
        "prefix": "06",
        "freq_uplink": "824-849MHz",
        "freq_downlink": "869-894MHz",
    },
    {
        "name": "PCS1900",
        "prefix": "07",
        "freq_uplink": "1850-1915MHz",
        "freq_downlink": "1930-1995MHz",
    },
    {
        "name": "AWS2100",
        "prefix": "08",
        "freq_uplink": "1710-1755MHz",
        "freq_downlink": "2110-2155MHz",
    },
]

# OID suffix mappings (appended to band prefix)
OID_RF_STATUS = "02"
OID_OUTPUT_POWER_UL = "11"
OID_OUTPUT_POWER_DL = "13"
OID_GAIN_UL = "14"
OID_GAIN_DL = "15"
OID_OVERLOAD_UL = "24"
OID_OVERLOAD_DL = "25"
OID_ISO_UL = "26"
OID_ISO_DL = "27"
OID_RF_SWITCH = "40"
OID_MGC_UL = "41"
OID_MGC_DL = "42"


class HiBoostAuthError(Exception):
    """Raised when HiBoost authentication fails."""


class HiBoostAPIError(Exception):
    """Raised when HiBoost API requests fail."""


class HiBoostClient:
    """Client for HiBoost Signal Supervisor cloud API."""

    TOKEN_REFRESH_MARGIN = 300  # seconds before token considered stale

    def __init__(
        self,
        account: str = "",
        password: str = "",
        api_url: str = "",
    ):
        env_account = os.getenv("HIBOOST_ACCOUNT", "")
        env_password = os.getenv("HIBOOST_PASSWORD", "")
        env_api_url = os.getenv("HIBOOST_API_URL", DEFAULT_API_URL)

        self.account = account or env_account
        self.password = password or env_password
        self.api_url = api_url or env_api_url
        self.timeout = 15

        self._session = requests.Session()
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._user_id: Optional[str] = None
        self._device_id: Optional[str] = None

        # Load RSA public key
        pub_key_bytes = base64.b64decode(RSA_PUBLIC_KEY_B64)
        self._rsa_key = load_der_public_key(pub_key_bytes)

    def set_credentials(self, account: str, password: str, api_url: str = ""):
        """Update credentials and clear cached auth."""
        self.account = account
        self.password = password
        if api_url:
            self.api_url = api_url
        self._token = None
        self._token_expires_at = None
        self._user_id = None
        self._device_id = None

    def _needs_login(self) -> bool:
        if not self._token or not self._token_expires_at:
            return True
        return datetime.utcnow() >= (
            self._token_expires_at - timedelta(seconds=self.TOKEN_REFRESH_MARGIN)
        )

    def _sha256(self, text: str) -> str:
        """SHA-256 hash, lowercase hex."""
        return hashlib.sha256(text.encode()).hexdigest().lower()

    def _rsa_encrypt(self, text: str) -> str:
        """RSA encrypt with PKCS1v15, return base64."""
        encrypted = self._rsa_key.encrypt(text.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode()

    def _x_server_host(self) -> str:
        """MD5 hash of api_url + port for X-Server-Host header."""
        return hashlib.md5((self.api_url + "443").encode()).hexdigest()

    def _headers(self) -> Dict[str, str]:
        headers = {"X-Server-Host": self._x_server_host()}
        if self._token:
            headers["Authorization"] = self._token
        return headers

    def authenticate(self) -> str:
        """Login and return auth token."""
        if not self.account or not self.password:
            raise HiBoostAuthError("Missing HiBoost credentials")

        sha256_pw = self._sha256(self.password)
        rsa_pw = self._rsa_encrypt(self.password)

        data = {
            "appType": 0,
            "client": "ANDROID",
            "account": self.account,
            "email": self.account,
            "password": sha256_pw,
            "rsaPassword": rsa_pw,
        }

        try:
            resp = self._session.post(
                f"{self.api_url}/app/authentication/login/app",
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Server-Host": self._x_server_host(),
                },
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise HiBoostAPIError(f"Connection failed: {e}") from e

        if resp.status_code != 200:
            raise HiBoostAuthError(f"HTTP {resp.status_code}")

        result = resp.json()
        code = result.get("code")
        if code != 200:
            msg = result.get("msg", "Unknown error")
            raise HiBoostAuthError(f"Login failed: {msg} (code {code})")

        user_data = result["data"]
        self._token = user_data["token"]
        self._user_id = user_data["id"]
        # Token expires in 10 days per JWT, refresh daily
        self._token_expires_at = datetime.utcnow() + timedelta(hours=24)
        logger.info(f"HiBoost authenticated as {user_data.get('name', self.account)}")
        return self._token

    def _get_token(self) -> str:
        if self._needs_login():
            return self.authenticate()
        return self._token

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET request to the HiBoost API. Retries once on 401."""
        self._get_token()
        for attempt in range(2):
            try:
                resp = self._session.get(
                    f"{self.api_url}{path}",
                    params=params,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                raise HiBoostAPIError(f"Request failed: {e}") from e

            # Handle HTTP-level or JSON-level 401 by re-authenticating once
            is_401 = resp.status_code == 401
            if not is_401 and resp.status_code == 200:
                data = resp.json()
                is_401 = data.get("code") == 401

            if is_401 and attempt == 0:
                logger.info("HiBoost token expired, re-authenticating")
                self._token = None
                self._token_expires_at = None
                self._get_token()
                continue

            if resp.status_code != 200:
                raise HiBoostAPIError(f"HTTP {resp.status_code}")

            data = resp.json()
            if data.get("code") != 200:
                raise HiBoostAPIError(f"API error: {data.get('msg')} (code {data.get('code')})")
            return data.get("data")

    def _post(self, path: str, data: Any = None, json_body: Any = None) -> Any:
        """POST request to the HiBoost API."""
        self._get_token()
        try:
            resp = self._session.post(
                f"{self.api_url}{path}",
                data=data,
                json=json_body,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise HiBoostAPIError(f"Request failed: {e}") from e

        if resp.status_code != 200:
            raise HiBoostAPIError(f"HTTP {resp.status_code}")

        result = resp.json()
        if result.get("code") != 200:
            raise HiBoostAPIError(f"API error: {result.get('msg')} (code {result.get('code')})")
        return result.get("data")

    def test_connection(self) -> Dict[str, Any]:
        """Test credentials by logging in and fetching dashboard."""
        token = self.authenticate()
        dashboard = self.get_dashboard()
        return {
            "success": True,
            "user_id": self._user_id,
            "device_count": len(dashboard.get("devices", [])),
            "online": dashboard.get("onlineTotal", 0),
        }

    def get_dashboard(self) -> Dict[str, Any]:
        """Get device dashboard (all devices overview)."""
        return self._get("/app/me/devices/dashboard")

    def get_device_detail(self, device_id: str) -> Dict[str, Any]:
        """Get full device details including params and model config."""
        return self._get(f"/app/me/devices/{device_id}", params={"apiVersion": "2"})

    def get_device_params(
        self, device_id: str, param_keys: str = "", slave_id: str = ""
    ) -> Dict[str, str]:
        """Get specific device parameters by OID keys."""
        params = {}
        if param_keys:
            params["paramKeys"] = param_keys
        if slave_id:
            params["slaveId"] = slave_id
        return self._get(f"/app/me/devices/{device_id}/params", params=params)

    def update_device_params(
        self, device_id: str, param_updates: List[Dict[str, str]], slave_id: str = ""
    ) -> Any:
        """Write device parameters (e.g., MGC gain, RF switch).

        Args:
            device_id: Device ID.
            param_updates: List of {"oid": "XXXX", "value": "XX", "syntax": "UINT1"} dicts.
            slave_id: Optional slave ID for multi-device setups.
        """
        self._get_token()
        import json as _json

        payload = _json.dumps(param_updates)
        params = {}
        if slave_id:
            params["slaveId"] = slave_id

        try:
            resp = self._session.post(
                f"{self.api_url}/app/me/devices/{device_id}/params",
                data=payload,
                params=params,
                headers={
                    **self._headers(),
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise HiBoostAPIError(f"Request failed: {e}") from e

        if resp.status_code != 200:
            raise HiBoostAPIError(f"HTTP {resp.status_code}")

        result = resp.json()
        if result.get("code") != 200:
            raise HiBoostAPIError(
                f"Param update failed: {result.get('msg')} (code {result.get('code')})"
            )
        return result.get("data")

    def close(self):
        """Close the HTTP session."""
        if self._session:
            self._session.close()
