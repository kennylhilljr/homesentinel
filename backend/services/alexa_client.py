"""
Alexa Smart Home API Client for HomeSentinel
Implements Login with Amazon OAuth and Alexa Smart Home Skill API v3
"""

import os
import logging
import time
import json
import requests
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlexaAuthError(Exception):
    """Raised when authentication fails"""
    pass


class AlexaAPIError(Exception):
    """Raised when an Alexa API call fails"""
    pass


class AlexaClient:
    """
    Alexa Smart Home API client
    Manages LWA OAuth tokens and Alexa Smart Home directives
    """

    LWA_AUTH_URL = "https://www.amazon.com/ap/oa"
    LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
    ALEXA_EVENT_GATEWAY = "https://api.amazonalexa.com/v3/events"
    ALEXA_ENDPOINT_API = "https://api.amazonalexa.com/v2/endpoints"

    TOKEN_REFRESH_MARGIN = 300  # 5 minutes

    def __init__(self):
        self.client_id = os.getenv("ALEXA_CLIENT_ID", "")
        self.client_secret = os.getenv("ALEXA_CLIENT_SECRET", "")
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._http_session = requests.Session()

        logger.info("AlexaClient initialized")

    def set_credentials(self, client_id: str, client_secret: str):
        """Update OAuth credentials"""
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = None
        self._refresh_token = None
        self._token_expiry = None

    def set_tokens(self, access_token: str, refresh_token: str, expires_in: int = 3600):
        """Set OAuth tokens directly (from callback)"""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
        logger.info(f"Alexa tokens set, expires at {self._token_expiry}")

    SKILL_ID = "amzn1.ask.skill.27c0694b-e2db-44a5-99e6-ab8a4410ba9c"

    def get_auth_url(self, redirect_uri: str) -> str:
        """Generate LWA authorization URL"""
        from urllib.parse import urlencode
        params = {
            "client_id": self.client_id,
            "scope": "profile",
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": str(uuid.uuid4()),
        }
        return f"{self.LWA_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        try:
            response = self._http_session.post(
                self.LWA_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                },
                timeout=10,
            )

            if response.status_code != 200:
                raise AlexaAuthError(f"Token exchange failed: {response.status_code} {response.text}")

            data = response.json()
            self._access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            self._token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600))

            logger.info("Alexa authorization code exchanged for tokens")
            return data

        except requests.RequestException as e:
            raise AlexaAuthError(f"Token exchange request failed: {e}")

    def _refresh_access_token(self):
        """Refresh the access token using the refresh token"""
        if not self._refresh_token:
            raise AlexaAuthError("No refresh token available")

        try:
            response = self._http_session.post(
                self.LWA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=10,
            )

            if response.status_code != 200:
                raise AlexaAuthError(f"Token refresh failed: {response.status_code}")

            data = response.json()
            self._access_token = data["access_token"]
            if "refresh_token" in data:
                self._refresh_token = data["refresh_token"]
            self._token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600))

            logger.info("Alexa access token refreshed")

        except requests.RequestException as e:
            raise AlexaAuthError(f"Token refresh request failed: {e}")

    def _get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary"""
        if not self._access_token:
            raise AlexaAuthError("Not authenticated. Please complete OAuth flow.")

        if self._token_expiry and datetime.now() >= self._token_expiry - timedelta(seconds=self.TOKEN_REFRESH_MARGIN):
            self._refresh_access_token()

        return self._access_token

    def is_authenticated(self) -> bool:
        """Check if we have valid tokens"""
        if not self._access_token or not self._refresh_token:
            return False
        return True

    def _send_directive(self, namespace: str, name: str, endpoint_id: Optional[str] = None,
                        payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Send an Alexa Smart Home directive"""
        token = self._get_valid_token()

        directive = {
            "directive": {
                "header": {
                    "namespace": namespace,
                    "name": name,
                    "messageId": str(uuid.uuid4()),
                    "payloadVersion": "3",
                },
                "payload": payload or {},
            }
        }

        if endpoint_id:
            directive["directive"]["endpoint"] = {
                "endpointId": endpoint_id,
                "scope": {
                    "type": "BearerToken",
                    "token": token,
                },
            }
        else:
            directive["directive"]["payload"]["scope"] = {
                "type": "BearerToken",
                "token": token,
            }

        try:
            response = self._http_session.post(
                self.ALEXA_EVENT_GATEWAY,
                json=directive,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

            if response.status_code == 401:
                self._refresh_access_token()
                token = self._access_token
                if endpoint_id:
                    directive["directive"]["endpoint"]["scope"]["token"] = token
                else:
                    directive["directive"]["payload"]["scope"]["token"] = token
                response = self._http_session.post(
                    self.ALEXA_EVENT_GATEWAY,
                    json=directive,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )

            if response.status_code != 200:
                raise AlexaAPIError(f"Directive failed: {response.status_code} {response.text}")

            return response.json()

        except requests.RequestException as e:
            raise AlexaAPIError(f"Directive request failed: {e}")

    def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover all Alexa smart home devices"""
        logger.info("Discovering Alexa devices")
        response = self._send_directive("Alexa.Discovery", "Discover")
        endpoints = response.get("event", {}).get("payload", {}).get("endpoints", [])
        logger.info(f"Discovered {len(endpoints)} Alexa devices")
        return endpoints

    def get_device_state(self, endpoint_id: str) -> Dict[str, Any]:
        """Get the current state of a device via ReportState"""
        logger.info(f"Getting state for device {endpoint_id}")
        try:
            response = self._send_directive("Alexa", "ReportState", endpoint_id=endpoint_id)
            properties = response.get("context", {}).get("properties", [])
            state = {}
            for prop in properties:
                ns = prop.get("namespace", "")
                name = prop.get("name", "")
                value = prop.get("value")
                key = f"{ns}.{name}"
                state[key] = {
                    "value": value,
                    "timeOfSample": prop.get("timeOfSample"),
                    "uncertaintyInMilliseconds": prop.get("uncertaintyInMilliseconds"),
                }
            return state
        except AlexaAPIError as e:
            logger.warning(f"Failed to get state for {endpoint_id}: {e}")
            return {}

    def send_power_command(self, endpoint_id: str, turn_on: bool) -> Dict[str, Any]:
        """Send power on/off command"""
        name = "TurnOn" if turn_on else "TurnOff"
        return self._send_directive("Alexa.PowerController", name, endpoint_id=endpoint_id)

    def set_brightness(self, endpoint_id: str, brightness: int) -> Dict[str, Any]:
        """Set brightness level (0-100)"""
        return self._send_directive(
            "Alexa.BrightnessController", "SetBrightness",
            endpoint_id=endpoint_id,
            payload={"brightness": max(0, min(100, brightness))},
        )

    def set_color(self, endpoint_id: str, hue: float, saturation: float, brightness: float) -> Dict[str, Any]:
        """Set light color (HSB)"""
        return self._send_directive(
            "Alexa.ColorController", "SetColor",
            endpoint_id=endpoint_id,
            payload={"color": {"hue": hue, "saturation": saturation, "brightness": brightness}},
        )

    def set_color_temperature(self, endpoint_id: str, temperature_k: int) -> Dict[str, Any]:
        """Set color temperature in Kelvin"""
        return self._send_directive(
            "Alexa.ColorTemperatureController", "SetColorTemperature",
            endpoint_id=endpoint_id,
            payload={"colorTemperatureInKelvin": temperature_k},
        )

    def set_thermostat(self, endpoint_id: str, target_temp: float, scale: str = "FAHRENHEIT") -> Dict[str, Any]:
        """Set thermostat target temperature"""
        return self._send_directive(
            "Alexa.ThermostatController", "SetTargetTemperature",
            endpoint_id=endpoint_id,
            payload={"targetSetpoint": {"value": target_temp, "scale": scale}},
        )

    def set_thermostat_mode(self, endpoint_id: str, mode: str) -> Dict[str, Any]:
        """Set thermostat mode (HEAT, COOL, AUTO, OFF)"""
        return self._send_directive(
            "Alexa.ThermostatController", "SetThermostatMode",
            endpoint_id=endpoint_id,
            payload={"thermostatMode": {"value": mode}},
        )

    def send_lock_command(self, endpoint_id: str, lock: bool) -> Dict[str, Any]:
        """Send lock/unlock command"""
        name = "Lock" if lock else "Unlock"
        return self._send_directive("Alexa.LockController", name, endpoint_id=endpoint_id)

    def get_endpoints(self, expand: bool = True) -> List[Dict[str, Any]]:
        """Get endpoints via the Endpoints API v2.

        When expand=True, includes connection objects with MAC addresses.
        See: https://developer.amazon.com/en-US/docs/alexa/alexa-smart-properties/endpoint-api.html
        """
        token = self._get_valid_token()
        params = {"owner": "~caller"}
        if expand:
            params["expand"] = "all"
        try:
            response = self._http_session.get(
                self.ALEXA_ENDPOINT_API,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )

            # Retry once with refreshed token on 401
            if response.status_code == 401:
                logger.info("Endpoints API 401, refreshing token and retrying")
                self._refresh_access_token()
                token = self._access_token
                response = self._http_session.get(
                    self.ALEXA_ENDPOINT_API,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )

            if response.status_code != 200:
                logger.warning(f"Endpoints API returned {response.status_code}: {response.text[:200]}")
                raise AlexaAPIError(f"Endpoints API failed: {response.status_code}")
            data = response.json()
            # API returns results in "results" or "endpoints" or "items"
            endpoints = data.get("results", data.get("endpoints", data.get("items", [])))
            logger.info(f"Endpoints API returned {len(endpoints)} endpoints (expand={expand})")
            return endpoints
        except requests.RequestException as e:
            raise AlexaAPIError(f"Endpoints request failed: {e}")

    def get_smart_home_devices_with_connections(self) -> List[Dict[str, Any]]:
        """Get smart home devices with MAC addresses via web API.

        Falls back to the cookie-based alexa.amazon.com/api/phoenix endpoint
        which can return connection info including MAC addresses for devices
        that report them (Echo, Fire TV, smart plugs, etc.).
        """
        if not self._cookies:
            raise AlexaAPIError("Browser cookies not configured")

        headers = self._get_alexa_web_headers()
        cookies = self._get_cookie_jar()

        devices_with_mac = []

        # Try the Phoenix device groups endpoint — returns more device details
        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/phoenix",
                headers=headers, cookies=cookies, timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                # Phoenix returns nested device data with network info
                network_detail = data.get("networkDetail", data)
                if isinstance(network_detail, dict):
                    for key, val in network_detail.items():
                        if isinstance(val, dict) and "macAddress" in val:
                            devices_with_mac.append(val)
                logger.info(f"Phoenix API returned data with {len(devices_with_mac)} MAC-bearing devices")
        except Exception as e:
            logger.warning(f"Phoenix API failed: {e}")

        # Also try the devices-v2 endpoint — Echo devices often have MAC in their data
        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/devices-v2/device",
                headers=headers, cookies=cookies, timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                raw_devices = data.get("devices", data) if isinstance(data, dict) else data
                if isinstance(raw_devices, list):
                    for d in raw_devices:
                        if isinstance(d, dict) and d.get("macAddress"):
                            devices_with_mac.append(d)
                    logger.info(f"Devices-v2 API: {len(raw_devices)} total, found MAC addresses in some")
        except Exception as e:
            logger.warning(f"Devices-v2 API failed for MAC fetch: {e}")

        return devices_with_mac

    # ---------- Alexa Web API (cookie-based device access) ----------
    # The alexa.amazon.com APIs require browser session cookies, not OAuth tokens.
    # This is the same approach used by Home Assistant's alexa_media_player
    # and the alexapy library.

    ALEXA_API_BASE = "https://alexa.amazon.com"
    _cookies: Optional[Dict[str, str]] = None
    _csrf_token: Optional[str] = None

    def set_cookies(self, cookie_string: str):
        """Set browser cookies for Alexa web API access.
        Accepts a cookie string (from browser DevTools) in the format:
        'session-id=xxx; ubid-main=xxx; at-main=xxx; ...'
        """
        self._cookies = {}
        for part in cookie_string.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                self._cookies[key.strip()] = value.strip()
        # Extract CSRF token if present
        self._csrf_token = self._cookies.get("csrf", "")
        logger.info(f"Alexa cookies set ({len(self._cookies)} cookies)")

    def has_cookies(self) -> bool:
        """Check if browser cookies are configured."""
        return bool(self._cookies)

    def _get_alexa_web_headers(self) -> Dict[str, str]:
        """Headers for Alexa web API calls using cookies."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Origin": "https://alexa.amazon.com",
            "Referer": "https://alexa.amazon.com/spa/index.html",
        }
        if self._csrf_token:
            headers["csrf"] = self._csrf_token
        return headers

    def _get_cookie_jar(self) -> Dict[str, str]:
        """Get cookies dict for requests."""
        return self._cookies or {}

    def get_smart_home_devices(self) -> List[Dict[str, Any]]:
        """Get all smart home devices via the Alexa behaviors/entities API.
        Requires browser cookies. Returns entities from all linked skills.
        """
        if not self._cookies:
            raise AlexaAPIError("Browser cookies not configured. Set cookies in Settings.")

        headers = self._get_alexa_web_headers()
        cookies = self._get_cookie_jar()

        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome",
                headers=headers, cookies=cookies, timeout=15,
            )
            logger.info(f"Behaviors/entities API returned {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info(f"Got {len(data)} smart home entities")
                    return data
                return []
            elif response.status_code == 401:
                raise AlexaAPIError("Cookies expired. Please update cookies in Settings.")
            else:
                logger.warning(f"Behaviors/entities returned {response.status_code}")
                return []
        except AlexaAPIError:
            raise
        except Exception as e:
            logger.warning(f"Behaviors/entities API failed: {e}")
            raise AlexaAPIError(f"Could not fetch smart home devices: {e}")

    def get_echo_devices_web(self) -> List[Dict[str, Any]]:
        """Get Echo/Alexa hardware devices via the web API."""
        if not self._cookies:
            return []
        headers = self._get_alexa_web_headers()
        cookies = self._get_cookie_jar()
        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/devices-v2/device",
                headers=headers, cookies=cookies, timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("devices", data) if isinstance(data, dict) else data
            logger.info(f"Echo devices API returned {response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Echo devices API failed: {e}")
            return []

    def get_device_wifi_details(self, serial_number: str, device_type: str) -> Optional[Dict[str, Any]]:
        """Get WiFi details (including MAC address) for a specific Echo/Fire device.

        Uses the undocumented /api/device-wifi-details endpoint (same as alexapy library).
        Returns dict with: deviceSerialNumber, deviceType, essid, macAddress
        Returns None if device is a group or doesn't have WiFi (HTTP 400).
        """
        if not self._cookies:
            return None
        headers = self._get_alexa_web_headers()
        cookies = self._get_cookie_jar()
        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/device-wifi-details",
                params={"deviceSerialNumber": serial_number, "deviceType": device_type},
                headers=headers, cookies=cookies, timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            # 400 = device groups, car integrations, etc. — not real hardware
            return None
        except Exception as e:
            logger.warning(f"device-wifi-details failed for {serial_number}: {e}")
            return None

    def get_all_device_macs(self) -> List[Dict[str, str]]:
        """Get MAC addresses for all Echo/Fire hardware devices.

        Calls devices-v2 to get the device list, then device-wifi-details
        for each device to get MAC addresses. Skips groups and non-hardware.
        Returns list of dicts with: serialNumber, accountName, deviceFamily,
        deviceType, macAddress (normalized aa:bb:cc:dd:ee:ff), essid
        """
        devices = self.get_echo_devices_web()
        if not devices:
            return []

        results = []
        for d in devices:
            if not isinstance(d, dict):
                continue
            serial = d.get("serialNumber", "")
            dtype = d.get("deviceType", "")
            name = d.get("accountName", "")
            family = d.get("deviceFamily", "")
            if not serial or not dtype:
                continue

            wifi = self.get_device_wifi_details(serial, dtype)
            if not wifi:
                continue
            mac_raw = wifi.get("macAddress", "")
            if not mac_raw or len(mac_raw) != 12:
                continue

            # Normalize: "ACCCFC637684" -> "ac:cc:fc:63:76:84"
            mac_normalized = ":".join(mac_raw[i:i+2].lower() for i in range(0, 12, 2))
            results.append({
                "serialNumber": serial,
                "accountName": name,
                "deviceFamily": family,
                "deviceType": dtype,
                "macAddress": mac_normalized,
                "essid": wifi.get("essid"),
            })

        logger.info(f"Got MAC addresses for {len(results)} of {len(devices)} Echo/Fire devices")
        return results

    def get_routines(self) -> List[Dict[str, Any]]:
        """Get Alexa routines via the web API."""
        if not self._cookies:
            return []
        headers = self._get_alexa_web_headers()
        cookies = self._get_cookie_jar()
        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/behaviors/automations",
                headers=headers, cookies=cookies, timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else data.get("automations", [])
            return []
        except Exception as e:
            logger.warning(f"Routines API failed: {e}")
            return []

    def test_cookies(self) -> Dict[str, Any]:
        """Test if the current cookies are valid by querying the bootstrap endpoint."""
        if not self._cookies:
            return {"success": False, "error": "No cookies configured"}
        headers = self._get_alexa_web_headers()
        cookies = self._get_cookie_jar()
        try:
            response = self._http_session.get(
                f"{self.ALEXA_API_BASE}/api/bootstrap",
                headers=headers, cookies=cookies, timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                auth = data.get("authentication", {})
                return {
                    "success": True,
                    "authenticated": auth.get("authenticated", False),
                    "customer_name": auth.get("customerName", ""),
                    "customer_id": auth.get("customerId", ""),
                }
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close(self):
        """Close HTTP session"""
        if self._http_session:
            self._http_session.close()
            logger.info("AlexaClient session closed")
