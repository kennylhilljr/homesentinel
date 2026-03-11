"""
Deco API Client for HomeSentinel
Implements TP-Link Deco API client with authentication and session management.
Supports both cloud API (wap.tplinkcloud.com) and local LAN API with RSA+AES encryption.

Cloud API: JSON-RPC POSTs to wap.tplinkcloud.com, token as query parameter.
Local API: RSA-encrypted password, AES-CBC encrypted request/response bodies,
           RSA-signed requests with sequence numbers.
"""

import os
import logging
import uuid
import json
import base64
import re
import requests
from binascii import b2a_hex
from hashlib import md5
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from Crypto.Cipher import AES, PKCS1_v1_5
    from Crypto.PublicKey import RSA
    from Crypto import Random
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

logger = logging.getLogger(__name__)


class InvalidCredentialsError(Exception):
    """Raised when authentication fails due to invalid credentials"""
    pass


class SessionExpiredError(Exception):
    """Raised when session token is expired"""
    pass


class APIConnectionError(Exception):
    """Raised when there are network or API connection issues"""
    pass


class DecoEncryption:
    """AES-CBC + RSA encryption for TP-Link Deco local API."""

    def __init__(self):
        self._key = b2a_hex(Random.get_random_bytes(8))  # 16-char hex key
        self._iv = b2a_hex(Random.get_random_bytes(8))    # 16-char hex IV

    def aes_encrypt(self, raw: str) -> str:
        raw = self._pad(raw)
        cipher = AES.new(self._key, AES.MODE_CBC, self._iv)
        return base64.b64encode(cipher.encrypt(raw.encode())).decode()

    def aes_decrypt(self, enc: str) -> str:
        enc = base64.b64decode(enc)
        cipher = AES.new(self._key, AES.MODE_CBC, self._iv)
        decrypted = cipher.decrypt(enc)
        return self._unpad(decrypted).decode()

    @staticmethod
    def rsa_encrypt(data: str, nn: str, ee: str) -> str:
        e = int(ee, 16)
        n = int(nn, 16)
        key = RSA.construct((n, e))
        cipher = PKCS1_v1_5.new(key)
        result = cipher.encrypt(data.encode())
        return b2a_hex(result).decode()

    def get_signature(self, seq: int, is_login: bool, hash_val: str, nn: str, ee: str) -> str:
        if is_login:
            s = '{}&h={}&s={}'.format(self._get_aes_string(), hash_val, seq)
        else:
            s = 'h={}&s={}'.format(hash_val, seq)

        sign = ''
        pos = 0
        while pos < len(s):
            sign += self.rsa_encrypt(s[pos:pos + 53], nn, ee)
            pos += 53
        return sign

    def _pad(self, s: str) -> str:
        pad_len = AES.block_size - len(s) % AES.block_size
        return s + pad_len * chr(pad_len)

    @staticmethod
    def _unpad(s: bytes) -> bytes:
        return s[:-s[-1]]

    def _get_aes_string(self) -> str:
        return 'k={}&i={}'.format(self._key.decode(), self._iv.decode())


class DecoClient:
    """
    Deco API client for TP-Link Deco devices.
    Manages authentication, session tokens, and API requests.
    Supports cloud API and local LAN API with RSA+AES encryption.
    """

    DEFAULT_CLOUD_ENDPOINT = "https://wap.tplinkcloud.com"
    DEFAULT_LOCAL_ENDPOINT = "http://192.168.12.188"

    TOKEN_REFRESH_MARGIN = 300  # 5 minutes
    SESSION_TIMEOUT = 3600  # 1 hour

    def __init__(
        self,
        cloud_endpoint: Optional[str] = None,
        local_endpoint: Optional[str] = None,
        use_cloud: bool = True,
        verify_ssl: bool = True,
    ):
        self.cloud_endpoint = cloud_endpoint or self.DEFAULT_CLOUD_ENDPOINT
        self.local_endpoint = local_endpoint or self.DEFAULT_LOCAL_ENDPOINT
        self.use_cloud = use_cloud
        self.active_endpoint = self.cloud_endpoint if use_cloud else self.local_endpoint

        if use_cloud:
            self.verify_ssl = True
        else:
            self.verify_ssl = verify_ssl
            if not verify_ssl:
                logger.warning(
                    "SSL certificate verification disabled for local API endpoint - "
                    "only use on trusted networks"
                )

        self._session_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._session_start: Optional[datetime] = None
        self._terminal_uuid: str = str(uuid.uuid4())
        self._regional_endpoint: Optional[str] = None

        # Local API encryption state
        self._encryption: Optional[DecoEncryption] = None
        self._stok: str = ""           # Session token for URL path
        self._sysauth: str = ""        # Cookie session token
        self._pwd_nn: str = ""         # RSA modulus for password encryption
        self._pwd_ee: str = ""         # RSA exponent for password encryption
        self._sig_nn: str = ""         # RSA modulus for request signatures
        self._sig_ee: str = ""         # RSA exponent for request signatures
        self._seq: int = 0             # Sequence number for request signing
        self._local_logged: bool = False

        self.username = os.getenv("DECO_USERNAME", "")
        self.password = os.getenv("DECO_PASSWORD", "")

        self._http_session = self._create_session()

        logger.info(
            f"DecoClient initialized - Using {'cloud' if use_cloud else 'local LAN'} API at {self.active_endpoint}"
        )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def authenticate(self, username: Optional[str] = None, password: Optional[str] = None) -> str:
        username = username or self.username
        password = password or self.password

        if not username or not password:
            raise InvalidCredentialsError(
                "TP-Link credentials not provided. Set DECO_USERNAME and DECO_PASSWORD environment variables."
            )

        # Store credentials for re-authentication
        self.username = username
        self.password = password

        try:
            if self.use_cloud:
                return self._authenticate_cloud(username, password)
            else:
                try:
                    return self._authenticate_local(username, password)
                except Exception as local_error:
                    logger.warning(
                        "Local Deco authentication failed (%s). Falling back to cloud API.",
                        local_error,
                    )
                    self.use_cloud = True
                    self.active_endpoint = self.cloud_endpoint
                    self.verify_ssl = True
                    return self._authenticate_cloud(username, password)
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"Failed to connect to Deco API: {e}")
        except requests.exceptions.Timeout as e:
            raise APIConnectionError(f"Authentication request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Authentication request failed: {e}")

    def _authenticate_cloud(self, username: str, password: str) -> str:
        """Authenticate via TP-Link cloud API (wap.tplinkcloud.com)."""
        payload = {
            "method": "login",
            "params": {
                "appType": "Kasa_Android",
                "cloudUserName": username,
                "cloudPassword": password,
                "terminalUUID": self._terminal_uuid,
            },
        }

        logger.info(f"Attempting cloud authentication to {self.active_endpoint}")
        response = self._http_session.post(
            self.active_endpoint,
            json=payload,
            timeout=15,
            verify=self.verify_ssl,
        )

        if response.status_code != 200:
            raise APIConnectionError(
                f"Authentication failed with HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        error_code = data.get("error_code", -1)

        if error_code != 0:
            msg = data.get("msg", "Unknown error")
            if error_code in (-20601, -20675):
                raise InvalidCredentialsError(f"Invalid TP-Link credentials: {msg}")
            raise APIConnectionError(f"TP-Link cloud error {error_code}: {msg}")

        result = data.get("result", {})
        token = result.get("token")
        if not token:
            raise InvalidCredentialsError("Authentication succeeded but no token in response")

        self._session_token = token
        self._session_start = datetime.now()
        self._token_expiry = self._session_start + timedelta(seconds=self.SESSION_TIMEOUT)

        logger.info(f"Cloud authenticated as {username}. Token expires at {self._token_expiry}")
        return token

    def _authenticate_local(self, username: str, password: str) -> str:
        """Authenticate via local Deco API using RSA+AES encryption.

        Flow:
        1. GET /login?form=keys → RSA public key for password encryption
        2. POST /login?form=auth → sequence number + RSA key for signatures
        3. RSA-encrypt password, AES-encrypt login body, RSA-sign request
        4. POST /login?form=login → encrypted response with stok + sysauth cookie
        """
        if not HAS_CRYPTO:
            raise APIConnectionError(
                "pycryptodome is required for local Deco API. Install with: pip install pycryptodome"
            )

        host = self.local_endpoint.rstrip("/")
        self._encryption = DecoEncryption()

        # Step 1: Get RSA keys for password encryption
        logger.info(f"Requesting password RSA keys from {host}")
        keys_url = f"{host}/cgi-bin/luci/;stok=/login?form=keys"
        response = self._http_session.post(
            keys_url,
            params={"operation": "read"},
            timeout=10,
            verify=self.verify_ssl,
        )
        try:
            data = response.json()
            pwd_keys = data["result"]["password"]
            self._pwd_nn = pwd_keys[0]
            self._pwd_ee = pwd_keys[1]
            logger.info(f"Got password RSA key (modulus length: {len(self._pwd_nn)} hex chars)")
        except Exception as e:
            raise APIConnectionError(f"Failed to get password RSA keys: {e}; Response: {response.text}")

        # Step 2: Get sequence number and signature RSA key
        logger.info("Requesting sequence number and signature RSA key")
        auth_url = f"{host}/cgi-bin/luci/;stok=/login?form=auth"
        response = self._http_session.post(
            auth_url,
            params={"operation": "read"},
            timeout=10,
            verify=self.verify_ssl,
        )
        try:
            data = response.json()
            result = data["result"]
            self._seq = int(result["seq"])
            sig_keys = result["key"]
            self._sig_nn = sig_keys[0]
            self._sig_ee = sig_keys[1]
            logger.info(f"Got sequence number: {self._seq}")
        except Exception as e:
            raise APIConnectionError(f"Failed to get auth sequence: {e}; Response: {response.text}")

        # Step 3: Encrypt password and build login request
        crypted_pwd = self._encryption.rsa_encrypt(password, self._pwd_nn, self._pwd_ee)

        login_data = json.dumps({
            "params": {"password": crypted_pwd},
            "operation": "login",
        })

        # AES-encrypt the login data and create RSA signature
        encrypted_data = self._encryption.aes_encrypt(login_data)
        data_len = len(encrypted_data)
        hash_val = md5((username + password).encode()).hexdigest()
        sign = self._encryption.get_signature(
            self._seq + data_len, True, hash_val, self._sig_nn, self._sig_ee
        )

        body = {"sign": sign, "data": encrypted_data}

        # Step 4: Send encrypted login request
        login_url = f"{host}/cgi-bin/luci/;stok=/login?form=login"
        logger.info(f"Sending encrypted login request to {login_url}")
        response = self._http_session.post(
            login_url,
            data=body,
            headers={"Content-Type": "application/json"},
            timeout=10,
            verify=self.verify_ssl,
        )

        if response.status_code == 403:
            # Reset state and retry once
            self._pwd_nn = ""
            self._pwd_ee = ""
            self._seq = 0
            raise InvalidCredentialsError("Login rejected (403). Keys may have expired.")

        if response.status_code != 200:
            raise APIConnectionError(f"Local login failed: HTTP {response.status_code}: {response.text}")

        # Step 5: Decrypt response and extract session tokens
        try:
            resp_data = response.json()
            decrypted = json.loads(self._encryption.aes_decrypt(resp_data["data"]))
            self._stok = decrypted["result"]["stok"]

            # Extract sysauth from Set-Cookie header
            cookie_header = response.headers.get("set-cookie", "")
            match = re.search(r'sysauth=([^;]+)', cookie_header)
            if match:
                self._sysauth = match.group(1)
            else:
                raise APIConnectionError("No sysauth cookie in login response")

            self._local_logged = True
            self._session_token = self._stok
            self._session_start = datetime.now()
            self._token_expiry = self._session_start + timedelta(seconds=self.SESSION_TIMEOUT)

            logger.info(f"Local Deco authenticated. stok={self._stok[:8]}..., sysauth={self._sysauth[:8]}...")
            return self._stok

        except (KeyError, json.JSONDecodeError) as e:
            raise InvalidCredentialsError(f"Failed to parse login response: {e}; Raw: {response.text}")

    def _local_encrypted_request(self, path: str, data: str, _retry: bool = False) -> Dict[str, Any]:
        """Make an encrypted request to the local Deco API.

        Uses the stok URL token, sysauth cookie, AES-encrypted body, and RSA signature.
        """
        if not self._local_logged or not self._stok:
            self.authenticate()

        host = self.local_endpoint.rstrip("/")
        url = f"{host}/cgi-bin/luci/;stok={self._stok}/{path}"

        # Encrypt the request data
        encrypted_data = self._encryption.aes_encrypt(data)
        data_len = len(encrypted_data)
        hash_val = md5((self.username + self.password).encode()).hexdigest()
        # Always include AES key/IV in signature (is_login=True) — matches reference implementation
        sign = self._encryption.get_signature(
            self._seq + data_len, True, hash_val, self._sig_nn, self._sig_ee
        )

        body = {"sign": sign, "data": encrypted_data}

        try:
            response = self._http_session.post(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                cookies={"sysauth": self._sysauth},
                timeout=10,
                verify=self.verify_ssl,
            )
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Local request failed: {e}")

        if response.status_code == 403:
            logger.warning(f"Local API 403 response body: {response.text[:200]}")
            logger.warning(f"Local API 403 request URL: {url}")
            if _retry:
                raise APIConnectionError("Local API session rejected after re-authentication (403)")
            # Session expired, re-authenticate once
            logger.warning("Local session expired (403), re-authenticating...")
            self._local_logged = False
            self._stok = ""
            self._sysauth = ""
            self.authenticate()
            return self._local_encrypted_request(path, data, _retry=True)

        if response.status_code != 200:
            raise APIConnectionError(f"Local API request failed: HTTP {response.status_code}: {response.text}")

        # Decrypt response
        try:
            resp_data = response.json()
            if "data" in resp_data:
                decrypted = json.loads(self._encryption.aes_decrypt(resp_data["data"]))
                # Check for error_code
                if "error_code" in decrypted and decrypted["error_code"] != 0:
                    raise APIConnectionError(f"Local API error: {decrypted}")
                return decrypted.get("result", decrypted)
            return resp_data
        except json.JSONDecodeError as e:
            raise APIConnectionError(f"Failed to decode local API response: {e}; Raw: {response.text}")

    def get_session_token(self) -> str:
        if self._should_refresh_token():
            logger.info("Session token approaching expiry, refreshing...")
            self.authenticate()
        if not self._session_token:
            self.authenticate()
        return self._session_token

    def is_authenticated(self) -> bool:
        if self.use_cloud:
            if not self._session_token or not self._token_expiry:
                return False
            return datetime.now() < self._token_expiry
        else:
            return self._local_logged and bool(self._stok)

    def _should_refresh_token(self) -> bool:
        if not self._token_expiry:
            return True
        time_until_expiry = (self._token_expiry - datetime.now()).total_seconds()
        return time_until_expiry <= self.TOKEN_REFRESH_MARGIN

    def _cloud_request(self, method: str, params: Optional[Dict[str, Any]] = None, use_regional: bool = False) -> Dict[str, Any]:
        """Make a TP-Link cloud API request."""
        token = self.get_session_token()
        payload: Dict[str, Any] = {"method": method}
        if params:
            payload["params"] = params

        endpoint = self.active_endpoint
        if use_regional and self._regional_endpoint:
            endpoint = self._regional_endpoint

        try:
            response = self._http_session.post(
                f"{endpoint}?token={token}",
                json=payload,
                timeout=15,
                verify=self.verify_ssl,
            )
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"Failed to connect: {e}")
        except requests.exceptions.Timeout as e:
            raise APIConnectionError(f"Request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Request failed: {e}")

        if response.status_code == 401:
            self._session_token = None
            self._token_expiry = None
            raise InvalidCredentialsError("Session token is invalid or expired")

        if response.status_code != 200:
            raise APIConnectionError(f"API request failed: HTTP {response.status_code}")

        data = response.json()
        error_code = data.get("error_code", -1)
        if error_code != 0:
            msg = data.get("msg", "Unknown error")
            raise APIConnectionError(f"Cloud API error {error_code}: {msg}")

        return data.get("result", data)

    def _local_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a local Deco API request using encrypted protocol."""
        # Use the encrypted local protocol
        request_data = json.dumps(data) if data else json.dumps({"operation": "read"})
        return self._local_encrypted_request(endpoint, request_data)

    @staticmethod
    def _decode_alias(alias: str) -> str:
        """Decode base64-encoded Deco device alias, return as-is if not base64."""
        if not alias:
            return alias
        try:
            decoded = base64.b64decode(alias).decode("utf-8")
            if decoded.isprintable():
                return decoded
        except Exception:
            pass
        return alias

    def get_device_list(self) -> List[Dict[str, Any]]:
        """Fetch list of TP-Link Deco devices."""
        if self.use_cloud:
            result = self._cloud_request("getDeviceList")
            devices = result.get("deviceList", [])
            for dev in devices:
                regional = dev.get("appServerUrl") or dev.get("appServerUrlV2")
                if regional:
                    self._regional_endpoint = regional
                    break
            for dev in devices:
                if "alias" in dev:
                    dev["alias"] = self._decode_alias(dev["alias"])
            return devices
        else:
            result = self._local_encrypted_request(
                "admin/device?form=device_list",
                json.dumps({"operation": "read"})
            )
            devices = result.get("device_list", [])
            # Decode base64 names
            for dev in devices:
                if "alias" in dev:
                    dev["alias"] = self._decode_alias(dev["alias"])
                if "name" in dev:
                    dev["name"] = self._decode_alias(dev["name"])
            return devices

    def get_node_list(self) -> List[Dict[str, Any]]:
        """Fetch list of Deco nodes."""
        return self.get_device_list()

    def get_client_list(self) -> List[Dict[str, Any]]:
        """Fetch list of connected clients.

        Cloud: passthrough may fail for HOMEWIFISYSTEM devices (err_code 4).
        Local: uses encrypted admin/client API directly.
        """
        if self.use_cloud:
            devices = self.get_device_list()
            all_clients = []
            for device in devices:
                device_id = device.get("deviceId")
                if not device_id or device.get("status") != 1:
                    continue
                try:
                    request_data = {
                        "method": "get",
                        "client_list": {"name": "client_list"},
                    }
                    result = self._cloud_request("passthrough", {
                        "deviceId": device_id,
                        "requestData": request_data,
                    }, use_regional=True)
                    response_data = result.get("responseData", {})
                    if isinstance(response_data, str):
                        try:
                            response_data = json.loads(response_data)
                        except json.JSONDecodeError:
                            response_data = {}

                    if isinstance(response_data, dict) and response_data.get("err_code", 0) != 0:
                        logger.info(f"Device {device_id} does not support cloud passthrough (err_code={response_data.get('err_code')})")
                        continue

                    clients = (
                        response_data.get("client_list", {}).get("client_list", [])
                        if isinstance(response_data.get("client_list"), dict)
                        else response_data.get("client_list", [])
                    ) or response_data.get("clients", [])
                    all_clients.extend(clients)
                except Exception as e:
                    logger.warning(f"Failed to get clients from device {device_id}: {e}")
            return all_clients
        else:
            result = self._local_encrypted_request(
                "admin/client?form=client_list",
                json.dumps({"operation": "read", "params": {"device_mac": "default"}})
            )
            clients = result.get("client_list", [])
            # Decode base64 client names
            for client in clients:
                if "name" in client:
                    client["name"] = self._decode_alias(client["name"])
            return clients

    def get_client_list_local(self) -> List[Dict[str, Any]]:
        """Fetch client list directly from local Deco API, regardless of use_cloud setting.

        Creates a separate DecoClient instance with its own HTTP session to avoid
        session conflicts with the main client (Deco only allows one session at a time).

        Note: The Deco local API requires username='admin' for the signature hash
        (md5(username+password)), even when using cloud account passwords.
        """
        if not HAS_CRYPTO:
            raise APIConnectionError("pycryptodome required for local API")

        logger.info("Creating temporary local DecoClient for client list fetch")
        local_client = DecoClient(
            local_endpoint=self.local_endpoint,
            use_cloud=False,
            verify_ssl=False,
        )
        # Deco local API always expects 'admin' as username in signature hash
        local_client.username = "admin"
        local_client.password = self.password

        try:
            local_client.authenticate()

            result = local_client._local_encrypted_request(
                "admin/client?form=client_list",
                json.dumps({"operation": "read", "params": {"device_mac": "default"}})
            )
            clients = result.get("client_list", [])
            for client in clients:
                if "name" in client:
                    client["name"] = self._decode_alias(client["name"])

            logger.info(f"Fetched {len(clients)} clients from local Deco API")
            return clients
        finally:
            local_client.close()

    def rename_client(self, mac_address: str, new_name: str) -> bool:
        """Rename a client device on the Deco router via local API.

        # 2026-03-09: Uses the same admin/client?form=client_list endpoint
        # as get_client_list_local, but with operation="write".
        # Deco expects MAC in AA-BB-CC-DD-EE-FF format and name base64-encoded.

        Args:
            mac_address: Client MAC in any format (will be normalized to AA-BB-CC-DD-EE-FF)
            new_name: New display name for the client
        Returns:
            True if rename succeeded
        """
        if not HAS_CRYPTO:
            raise APIConnectionError("pycryptodome required for local API")

        # Normalize MAC to Deco format: AA-BB-CC-DD-EE-FF
        mac_clean = mac_address.lower().replace(":", "").replace("-", "").replace(" ", "")
        if len(mac_clean) != 12:
            raise ValueError(f"Invalid MAC address: {mac_address}")
        deco_mac = "-".join(mac_clean[i:i+2].upper() for i in range(0, 12, 2))

        # Deco stores names as base64
        name_encoded = base64.b64encode(new_name.encode("utf-8")).decode("ascii")

        logger.info(f"Renaming Deco client {deco_mac} to '{new_name}'")
        local_client = DecoClient(
            local_endpoint=self.local_endpoint,
            use_cloud=False,
            verify_ssl=False,
        )
        local_client.username = "admin"
        local_client.password = self.password

        try:
            local_client.authenticate()
            result = local_client._local_encrypted_request(
                "admin/client?form=client_list",
                json.dumps({
                    "operation": "write",
                    "params": {
                        "device_mac": "default",
                        "client_list": [{
                            "mac": deco_mac,
                            "name": name_encoded,
                        }]
                    }
                })
            )
            logger.info(f"Deco rename result: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename Deco client {deco_mac}: {e}")
            raise
        finally:
            local_client.close()

    # 2026-03-10: Toggle client_mesh (mesh steering) for a specific client device.
    def set_client_mesh(self, mac_address: str, mesh_enabled: bool) -> Dict[str, Any]:
        """Toggle mesh steering for a client device via local Deco API.

        Args:
            mac_address: Client MAC in any format (will be normalized to AA-BB-CC-DD-EE-FF)
            mesh_enabled: True to enable mesh, False to disable
        Returns:
            API response dict
        """
        if not HAS_CRYPTO:
            raise APIConnectionError("pycryptodome required for local API")

        mac_clean = mac_address.lower().replace(":", "").replace("-", "").replace(" ", "")
        if len(mac_clean) != 12:
            raise ValueError(f"Invalid MAC address: {mac_address}")
        deco_mac = "-".join(mac_clean[i:i+2].upper() for i in range(0, 12, 2))

        logger.info(f"Setting client_mesh={mesh_enabled} for {deco_mac}")
        local_client = DecoClient(
            local_endpoint=self.local_endpoint,
            use_cloud=False,
            verify_ssl=False,
        )
        local_client.username = "admin"
        local_client.password = self.password

        try:
            local_client.authenticate()
            result = local_client._local_encrypted_request(
                "admin/client?form=client_list",
                json.dumps({
                    "operation": "write",
                    "params": {
                        "device_mac": "default",
                        "client_list": [{
                            "mac": deco_mac,
                            "client_mesh": mesh_enabled,
                        }]
                    }
                })
            )
            logger.info(f"set_client_mesh result for {deco_mac}: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to set client_mesh for {deco_mac}: {e}")
            raise
        finally:
            local_client.close()

    def get_wifi_settings(self) -> Dict[str, Any]:
        """Fetch WiFi configuration settings."""
        if self.use_cloud:
            devices = self.get_device_list()
            if not devices:
                return {"error": "No devices found"}
            device_id = devices[0].get("deviceId")
            request_data = {
                "method": "get",
                "wireless": {"name": "wireless"},
            }
            result = self._cloud_request("passthrough", {
                "deviceId": device_id,
                "requestData": request_data,
            })
            return result.get("responseData", {})
        else:
            return self._local_encrypted_request(
                "admin/wireless?form=wlan",
                json.dumps({"operation": "read"})
            )

    def get_network_performance(self) -> Dict[str, Any]:
        """Fetch CPU/memory usage from local Deco API."""
        if self.use_cloud:
            return {"error": "Performance data only available via local API"}
        return self._local_encrypted_request(
            "admin/network?form=performance",
            json.dumps({"operation": "read"})
        )

    def get_wan_info(self) -> Dict[str, Any]:
        """Fetch WAN IPv4 info from local Deco API."""
        if self.use_cloud:
            return {"error": "WAN info only available via local API"}
        return self._local_encrypted_request(
            "admin/network?form=wan_ipv4",
            json.dumps({"operation": "read"})
        )

    def logout_local(self) -> None:
        """Logout from local Deco API."""
        if self._local_logged and self._stok:
            try:
                self._local_encrypted_request(
                    "admin/system?form=logout",
                    json.dumps({"operation": "logout"})
                )
            except Exception as e:
                logger.warning(f"Local logout failed: {e}")
            finally:
                self._stok = ""
                self._sysauth = ""
                self._local_logged = False

    def close(self) -> None:
        if not self.use_cloud and self._local_logged:
            self.logout_local()
        if self._http_session:
            self._http_session.close()
            logger.info("DecoClient session closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        auth_status = "authenticated" if self.is_authenticated() else "not authenticated"
        endpoint_type = "cloud" if self.use_cloud else "local LAN"
        return f"DecoClient({endpoint_type}, {auth_status})"
