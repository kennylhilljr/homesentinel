"""
Deco API Client for HomeSentinel
Implements TP-Link Deco API client with authentication and session management
Supports both cloud API and local LAN API endpoints
"""

import os
import logging
import time
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


class DecoClient:
    """
    Deco API client for TP-Link Deco devices
    Manages authentication, session tokens, and API requests
    """

    # Default endpoints
    DEFAULT_CLOUD_ENDPOINT = "https://api.tplinkcloud.com"
    DEFAULT_LOCAL_ENDPOINT = "http://192.168.0.1:8080"

    # Token refresh margin (refresh if token expires within this many seconds)
    TOKEN_REFRESH_MARGIN = 300  # 5 minutes

    # Session timeout (1 hour as per TP-Link API standard)
    SESSION_TIMEOUT = 3600  # seconds

    def __init__(
        self,
        cloud_endpoint: Optional[str] = None,
        local_endpoint: Optional[str] = None,
        use_cloud: bool = True,
    ):
        """
        Initialize Deco API client

        Args:
            cloud_endpoint: Cloud API endpoint URL (default: https://api.tplinkcloud.com)
            local_endpoint: Local LAN API endpoint URL (default: http://192.168.0.1:8080)
            use_cloud: If True, use cloud API; if False, use local LAN API
        """
        self.cloud_endpoint = cloud_endpoint or self.DEFAULT_CLOUD_ENDPOINT
        self.local_endpoint = local_endpoint or self.DEFAULT_LOCAL_ENDPOINT
        self.use_cloud = use_cloud
        self.active_endpoint = self.cloud_endpoint if use_cloud else self.local_endpoint

        # Session management
        self._session_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._session_start: Optional[datetime] = None

        # Credentials (loaded from environment)
        self.username = os.getenv("DECO_USERNAME", "")
        self.password = os.getenv("DECO_PASSWORD", "")

        # HTTP session with retry logic
        self._http_session = self._create_session()

        logger.info(
            f"DecoClient initialized - Using {'cloud' if use_cloud else 'local LAN'} API at {self.active_endpoint}"
        )

    def _create_session(self) -> requests.Session:
        """
        Create an HTTP session with retry logic

        Returns:
            Configured requests.Session with retry strategy
        """
        session = requests.Session()

        # Configure retry strategy
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
        """
        Authenticate with TP-Link Deco API

        Args:
            username: TP-Link account username (uses DECO_USERNAME env var if not provided)
            password: TP-Link account password (uses DECO_PASSWORD env var if not provided)

        Returns:
            Session token string

        Raises:
            InvalidCredentialsError: If authentication fails
            APIConnectionError: If unable to connect to API
        """
        # Use provided credentials or fall back to environment variables
        username = username or self.username
        password = password or self.password

        if not username or not password:
            raise InvalidCredentialsError(
                "TP-Link credentials not provided. Set DECO_USERNAME and DECO_PASSWORD environment variables."
            )

        try:
            # Prepare authentication payload
            payload = {"username": username, "password": password}

            # Make authentication request
            logger.info(f"Attempting authentication to {self.active_endpoint}")
            response = self._http_session.post(
                f"{self.active_endpoint}/api/auth/login",
                json=payload,
                timeout=10,
                verify=False,  # Disable SSL verification for local API
            )

            # Check for HTTP errors
            if response.status_code == 401:
                logger.warning(f"Authentication failed for user {username}: Invalid credentials")
                raise InvalidCredentialsError("Invalid TP-Link credentials provided")

            if response.status_code != 200:
                logger.error(f"Authentication request failed with status {response.status_code}")
                raise APIConnectionError(
                    f"Authentication failed with status {response.status_code}: {response.text}"
                )

            # Parse response
            data = response.json()

            # Extract token from response
            token = data.get("token") or data.get("sessionToken") or data.get("access_token")

            if not token:
                logger.error(f"No token found in authentication response: {data}")
                raise InvalidCredentialsError("Authentication succeeded but no token in response")

            # Update session state
            self._session_token = token
            self._session_start = datetime.now()
            self._token_expiry = self._session_start + timedelta(seconds=self.SESSION_TIMEOUT)

            logger.info(
                f"Successfully authenticated as {username}. Token expires at {self._token_expiry}"
            )

            return token

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during authentication: {e}")
            raise APIConnectionError(f"Failed to connect to Deco API: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout during authentication: {e}")
            raise APIConnectionError(f"Authentication request timed out: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during authentication: {e}")
            raise APIConnectionError(f"Authentication request failed: {e}")

    def get_session_token(self) -> str:
        """
        Get current valid session token, refreshing if necessary

        Returns:
            Valid session token string

        Raises:
            InvalidCredentialsError: If no credentials available
            SessionExpiredError: If token is expired and cannot be refreshed
            APIConnectionError: If refresh fails due to network issues
        """
        # Check if we need to refresh the token
        if self._should_refresh_token():
            logger.info("Session token approaching expiry, refreshing...")
            self.authenticate()

        if not self._session_token:
            logger.warning("No active session token, attempting authentication")
            self.authenticate()

        return self._session_token

    def is_authenticated(self) -> bool:
        """
        Check if current session is valid and not expired

        Returns:
            True if authenticated and token is valid, False otherwise
        """
        if not self._session_token or not self._token_expiry:
            return False

        if datetime.now() >= self._token_expiry:
            logger.debug("Session token has expired")
            return False

        return True

    def _should_refresh_token(self) -> bool:
        """
        Check if token should be refreshed

        Returns:
            True if token is expired or approaching expiry
        """
        if not self._token_expiry:
            return True

        time_until_expiry = (self._token_expiry - datetime.now()).total_seconds()
        return time_until_expiry <= self.TOKEN_REFRESH_MARGIN

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request with session token

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., '/api/nodes/list')
            data: JSON payload for POST/PUT requests
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            InvalidCredentialsError: If authentication is required
            APIConnectionError: If request fails
        """
        # Ensure we have a valid token
        token = self.get_session_token()

        try:
            # Prepare headers with authentication token
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Construct full URL
            url = f"{self.active_endpoint}{endpoint}"

            logger.debug(f"Making {method} request to {endpoint}")

            # Make request
            if method.upper() == "GET":
                response = self._http_session.get(
                    url, headers=headers, params=params, timeout=10, verify=False
                )
            elif method.upper() == "POST":
                response = self._http_session.post(
                    url, json=data, headers=headers, params=params, timeout=10, verify=False
                )
            elif method.upper() == "PUT":
                response = self._http_session.put(
                    url, json=data, headers=headers, params=params, timeout=10, verify=False
                )
            elif method.upper() == "DELETE":
                response = self._http_session.delete(
                    url, headers=headers, params=params, timeout=10, verify=False
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Check for authentication errors
            if response.status_code == 401:
                logger.warning("Received 401 Unauthorized, token may have been invalidated")
                self._session_token = None
                self._token_expiry = None
                raise InvalidCredentialsError("Session token is invalid or expired")

            if response.status_code != 200:
                logger.error(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
                raise APIConnectionError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            return response.json()

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during API request: {e}")
            raise APIConnectionError(f"Failed to connect to Deco API: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout during API request: {e}")
            raise APIConnectionError(f"API request timed out: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during API request: {e}")
            raise APIConnectionError(f"API request failed: {e}")

    def get_node_list(self) -> List[Dict[str, Any]]:
        """
        Fetch list of Deco nodes

        Returns:
            List of node information dictionaries

        Raises:
            InvalidCredentialsError: If session is invalid
            APIConnectionError: If API request fails
        """
        logger.info("Fetching Deco node list")
        response = self._make_request("GET", "/api/nodes/list")
        nodes = response.get("nodes", [])
        logger.info(f"Retrieved {len(nodes)} Deco nodes")
        return nodes

    def get_client_list(self) -> List[Dict[str, Any]]:
        """
        Fetch list of connected clients

        Returns:
            List of client information dictionaries

        Raises:
            InvalidCredentialsError: If session is invalid
            APIConnectionError: If API request fails
        """
        logger.info("Fetching connected client list")
        response = self._make_request("GET", "/api/clients/list")
        clients = response.get("clients", [])
        logger.info(f"Retrieved {len(clients)} connected clients")
        return clients

    def get_wifi_settings(self) -> Dict[str, Any]:
        """
        Fetch WiFi configuration settings

        Returns:
            WiFi settings dictionary

        Raises:
            InvalidCredentialsError: If session is invalid
            APIConnectionError: If API request fails
        """
        logger.info("Fetching WiFi settings")
        response = self._make_request("GET", "/api/wifi/settings")
        return response

    def update_wifi_settings(
        self,
        ssid: Optional[str] = None,
        password: Optional[str] = None,
        band_steering: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update WiFi configuration settings

        Args:
            ssid: New SSID/network name
            password: New WiFi password
            band_steering: Enable/disable band steering

        Returns:
            Updated settings response

        Raises:
            InvalidCredentialsError: If session is invalid
            APIConnectionError: If API request fails
        """
        # Build payload with provided settings
        payload: Dict[str, Any] = {}
        if ssid is not None:
            payload["ssid"] = ssid
        if password is not None:
            payload["password"] = password
        if band_steering is not None:
            payload["band_steering"] = band_steering

        if not payload:
            logger.warning("No WiFi settings provided for update")
            return {"message": "No settings to update"}

        logger.info(f"Updating WiFi settings: {list(payload.keys())}")
        response = self._make_request("PUT", "/api/wifi/settings", data=payload)
        return response

    def close(self) -> None:
        """Close HTTP session and clean up resources"""
        if self._http_session:
            self._http_session.close()
            logger.info("DecoClient session closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __repr__(self) -> str:
        """String representation"""
        auth_status = "authenticated" if self.is_authenticated() else "not authenticated"
        endpoint_type = "cloud" if self.use_cloud else "local LAN"
        return f"DecoClient({endpoint_type}, {auth_status})"
