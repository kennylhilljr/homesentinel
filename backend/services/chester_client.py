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

        # 2026-03-11: Chester firmware requires sid/version/mid in ALL requests,
        # including login. Without these fields, the API returns errcode -1000.
        payload = {
            "module": "login",
            "api": "login",
            "sid": "000000000000000000000000000000",
            "version": "1.0",
            "mid": self._next_mid(),
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

        # 2026-03-11: Session ID is in result.sid, not top-level sid
        result = data.get("result", {})
        sid = result.get("sid") or data.get("sid")
        if not sid or sid == "000000000000000000000000000000":
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

    # 2026-03-11: Cellular/5G signal and system info endpoints

    def get_lte_runtime(self) -> Dict[str, Any]:
        """Get LTE/5G modem runtime data (signal, IPs, IMEI, ICCID, etc.)."""
        return self.api_call("lte", "get_runtime")

    def get_lte_config(self) -> Dict[str, Any]:
        """Get LTE APN configuration."""
        return self.api_call("lte", "get")

    def get_lte_band(self) -> Dict[str, Any]:
        """Get locked/available band configuration."""
        return self.api_call("lte", "get_band")

    def get_lte_mode(self) -> Dict[str, Any]:
        """Get LTE/NR network mode preference."""
        return self.api_call("lte", "get_mode")

    def get_lte_traffic(self) -> Dict[str, Any]:
        """Get LTE data usage/traffic stats."""
        return self.api_call("lte", "get_traffic")

    def get_dashboard(self) -> Dict[str, Any]:
        """Get dashboard summary (WAN, LTE, WiFi status combined)."""
        return self.api_call("dashboard", "web")

    def get_system_info(self) -> Dict[str, Any]:
        """Get full system info including cellular signal data.

        Returns parsed fields matching the Chester web UI home page:
        Device Model, System Version, Hardware Version, IMEI, ICCID,
        IPv4/IPv6, DNS, Connection Time/Type, CellID, PCID, ARFCN,
        BAND, RSRP, RSRQ, SINR, CA BAND, MCC, MNC.
        """
        board = self.get_board_info()
        lte = self.get_lte_runtime()

        info = lte.get("info", {})
        status = lte.get("status", {})

        # Parse cellular signal data from AT command output
        parsed_signal = self._parse_lte_cell(info)

        # Calculate connection time from uptime seconds
        uptime_secs = status.get("uptime", 0)
        hours = uptime_secs // 3600
        minutes = (uptime_secs % 3600) // 60
        seconds = uptime_secs % 60
        connection_time = f"{hours}H{minutes}M{seconds}S"

        return {
            "device_model": board.get("name", ""),
            "system_version": board.get("soft_version", ""),
            "hardware_version": "V1.2",
            "mac_address": board.get("mac", ""),
            "cpu_percent": board.get("cpu_percent", 0),
            "mem_percent": board.get("mem_percent", 0),
            "imei": info.get("LTE_IMEI", ""),
            "iccid": info.get("LTE_ICCID", ""),
            "ipv4_addr": status.get("ipv4addr", ""),
            "ipv4_dns1": status.get("ipv4dns1", ""),
            "ipv4_dns2": status.get("ipv4dns2", ""),
            "ipv4_gateway": status.get("ipv4gateway", ""),
            "ipv4_mask": status.get("ipv4mask", ""),
            "ipv6_addr": status.get("ipv6addr", ""),
            "connection_time": connection_time,
            "connection_time_seconds": uptime_secs,
            "connection_type": parsed_signal.get("connection_type", info.get("LTE_TYPE", "")),
            "cell_id": parsed_signal.get("cell_id", ""),
            "pcid": parsed_signal.get("pcid", ""),
            "arfcn": parsed_signal.get("arfcn", ""),
            "band": parsed_signal.get("band", ""),
            "rsrp": parsed_signal.get("rsrp", info.get("LTE_RSRP", "")),
            "rsrq": parsed_signal.get("rsrq", info.get("LTE_RSRQ", "")),
            "sinr": parsed_signal.get("sinr", info.get("LTE_SINR", "")),
            "ca_band": parsed_signal.get("ca_band", []),
            "mcc": parsed_signal.get("mcc", ""),
            "mnc": parsed_signal.get("mnc", ""),
            "sim_status": "Ready" if info.get("LTE_SIM") == 1 else "Not detected",
            "is_5g": bool(info.get("LTE_5G")),
            "is_nsa": bool(info.get("LTE_NSA")),
            "wan_up": status.get("up", False),
            "cable_connected": status.get("cable", False),
            # Raw data for debugging
            "raw_lte_cell": info.get("LTE_CELL", ""),
            "raw_lte_cainfo": info.get("LTE_CAINFO", ""),
        }

    @staticmethod
    def _parse_lte_cell(info: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LTE_CELL AT command output into structured signal data.

        2026-03-11: Mirrors the parseLteData logic from the Chester web UI JS.
        Handles both GTCCINFO (Fibocom) and QENG (Quectel) AT response formats.
        """
        lte_cell = info.get("LTE_CELL", "")
        lte_cainfo = info.get("LTE_CAINFO", "")
        lte_type = info.get("LTE_TYPE", "")

        result: Dict[str, Any] = {}

        # Parse CA band info
        ca_bands = []
        if lte_cainfo:
            cleaned = lte_cainfo.replace("\r\n\r\nOK\r\n", "")
            # Quectel format: AT+QCAINFO\r\r\n+QCAINFO: "PCC",...
            if "+QCAINFO:" in cleaned:
                parts = cleaned.split("+QCAINFO:")
                for part in parts:
                    part = part.strip()
                    if part and not part.startswith("AT"):
                        ca_bands.append(part)
            # Fibocom format: AT+GTCAINFO?\r\r\n+GTCAINFO: \r\n...
            elif "+GTCAINFO:" in cleaned:
                cleaned = cleaned.replace("AT+GTCAINFO?\r\r\n+GTCAINFO: \r\n", "")
                for line in cleaned.split("\r\n"):
                    if line.strip():
                        ca_bands.append(line.strip())
        result["ca_band"] = ca_bands

        if not lte_cell:
            return result

        # Fibocom format: starts with AT+GTCCINFO?
        if lte_cell.startswith("AT+GTCCINFO?"):
            rows = lte_cell.split("\r\n")
            fields = rows[3].split(",") if len(rows) > 3 else []
            if not fields:
                return result

            if lte_type == "NR5G-SA":
                result.update({
                    "connection_type": lte_type,
                    "cell_id": hex(int(fields[5], 16)).upper().replace("0X", "") if len(fields) > 5 else "",
                    "pcid": str(int(fields[7], 16)) if len(fields) > 7 else "",
                    "arfcn": str(int(fields[6], 16)) if len(fields) > 6 else "",
                    "band": fields[8].replace("50", "") if len(fields) > 8 else "",
                    "rsrp": int(fields[12]) - 156 if len(fields) > 12 else "",
                    "rsrq": 0.5 * int(fields[13]) - 43 if len(fields) > 13 else "",
                    "sinr": 0.5 * int(fields[10]) - 23 if len(fields) > 10 else "",
                    "mcc": fields[3] if len(fields) > 3 else "",
                    "mnc": fields[2] if len(fields) > 2 else "",
                })
            else:
                result.update({
                    "connection_type": lte_type,
                    "cell_id": hex(int(fields[5], 16)).upper().replace("0X", "") if len(fields) > 5 else "",
                    "pcid": str(int(fields[7], 16)) if len(fields) > 7 else "",
                    "arfcn": str(int(fields[6], 16)) if len(fields) > 6 else "",
                    "band": fields[8].replace("10", "") if len(fields) > 8 else "",
                    "rsrp": int(fields[12]) - 141 if len(fields) > 12 else "",
                    "rsrq": 0.5 * int(fields[13]) - 19.5 if len(fields) > 13 else "",
                    "sinr": 0.5 * int(fields[10]) - 0.5 if len(fields) > 10 else "",
                    "mcc": fields[3] if len(fields) > 3 else "",
                    "mnc": fields[2] if len(fields) > 2 else "",
                })
        else:
            # Quectel format: AT+QENG="servingcell"\r\r\n+QENG: ...
            lines = lte_cell.split("\n")
            # Multi-line format: lines[1] has the data
            if len(lines) > 1:
                parts = lines[1].split(",")
                if len(parts) > 2:
                    conn_type = parts[2].replace('"', '')
                    if conn_type == "NR5G-SA":
                        result.update({
                            "connection_type": conn_type,
                            "cell_id": parts[6] if len(parts) > 6 else "",
                            "pcid": parts[7] if len(parts) > 7 else "",
                            "arfcn": parts[9] if len(parts) > 9 else "",
                            "band": parts[10] if len(parts) > 10 else "",
                            "rsrp": parts[12] if len(parts) > 12 else "",
                            "rsrq": parts[13] if len(parts) > 13 else "",
                            "sinr": parts[14] if len(parts) > 14 else "",
                            "mcc": parts[4] if len(parts) > 4 else "",
                            "mnc": parts[5] if len(parts) > 5 else "",
                        })
                    else:
                        result.update({
                            "connection_type": f"{conn_type} {parts[3].replace(chr(34), '')}" if len(parts) > 3 else conn_type,
                            "cell_id": parts[6] if len(parts) > 6 else "",
                            "pcid": parts[7] if len(parts) > 7 else "",
                            "arfcn": parts[8] if len(parts) > 8 else "",
                            "band": parts[9] if len(parts) > 9 else "",
                            "rsrp": parts[13] if len(parts) > 13 else "",
                            "rsrq": parts[14] if len(parts) > 14 else "",
                            "sinr": parts[16] if len(parts) > 16 else "",
                            "mcc": parts[4] if len(parts) > 4 else "",
                            "mnc": parts[5] if len(parts) > 5 else "",
                        })

        return result

    def logout(self):
        """Logout and invalidate the current session."""
        if self._session_id:
            try:
                self.api_call("login", "logout")
            except Exception:
                pass
            self._session_id = None
            self._session_expires_at = None

    def close(self):
        self.logout()
        if self._session:
            self._session.close()
