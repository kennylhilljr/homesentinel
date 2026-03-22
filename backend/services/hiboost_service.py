"""
HiBoost Signal Booster service for HomeSentinel.

Wraps the HiBoost cloud client with caching and data enrichment.
Translates raw hex OID values into human-readable RF parameters.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from services.hiboost_client import (
    BANDS,
    HiBoostAPIError,
    HiBoostAuthError,
    HiBoostClient,
    OID_GAIN_DL,
    OID_GAIN_UL,
    OID_ISO_DL,
    OID_ISO_UL,
    OID_MGC_DL,
    OID_MGC_UL,
    OID_OUTPUT_POWER_DL,
    OID_OUTPUT_POWER_UL,
    OID_OVERLOAD_DL,
    OID_OVERLOAD_UL,
    OID_RF_STATUS,
    OID_RF_SWITCH,
)

logger = logging.getLogger(__name__)

# Cache TTL in seconds
CACHE_TTL = 30


def _hex_to_uint(hex_str: str) -> int:
    """Convert hex string to unsigned int."""
    if not hex_str or hex_str == "--" or hex_str == "-":
        return 0
    return int(hex_str, 16)


def _hex_to_sint(hex_str: str) -> int:
    """Convert hex string to signed int (SINT1 = signed byte)."""
    if not hex_str or hex_str == "--" or hex_str == "-":
        return 0
    val = int(hex_str, 16)
    if val > 127:
        val -= 256
    return val


def _uint_to_hex(val: int) -> str:
    """Convert unsigned int to 2-char hex string."""
    return f"{val & 0xFF:02X}"


class HiBoostService:
    """Service layer for HiBoost signal booster integration."""

    def __init__(self, client: HiBoostClient):
        self.client = client
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < CACHE_TTL

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = value
        self._cache_ts[key] = time.time()

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._cache_ts.clear()

    def get_dashboard(self) -> Dict[str, Any]:
        """Get device dashboard with device list."""
        if self._is_cached("dashboard"):
            return self._cache["dashboard"]
        data = self.client.get_dashboard()
        self._set_cache("dashboard", data)
        return data

    def get_device_list(self) -> List[Dict[str, Any]]:
        """Get list of all registered devices."""
        dashboard = self.get_dashboard()
        return dashboard.get("devices", [])

    def get_device_detail(self, device_id: str) -> Dict[str, Any]:
        """Get full device detail with parsed RF parameters."""
        cache_key = f"detail:{device_id}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        raw = self.client.get_device_detail(device_id)
        detail = self._parse_device_detail(raw)
        self._set_cache(cache_key, detail)
        return detail

    def get_rf_params(self, device_id: str) -> Dict[str, Any]:
        """Get all RF parameters for all bands, parsed into readable format."""
        detail = self.get_device_detail(device_id)
        return {
            "device_id": device_id,
            "device_name": detail.get("name", ""),
            "model": detail.get("model", ""),
            "serial_number": detail.get("serial_number", ""),
            "firmware": detail.get("firmware", ""),
            "state": detail.get("state", ""),
            "bands": detail.get("bands", []),
            "connection": detail.get("connection", {}),
            "temperature": detail.get("temperature"),
        }

    def get_band_params(self, device_id: str, band_name: str) -> Optional[Dict[str, Any]]:
        """Get RF parameters for a specific band."""
        rf = self.get_rf_params(device_id)
        for band in rf.get("bands", []):
            if band["name"] == band_name:
                return band
        return None

    def update_mgc(
        self,
        device_id: str,
        band_name: str,
        mgc_ul: Optional[int] = None,
        mgc_dl: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update MGC (Manual Gain Control) for a band.

        Args:
            device_id: Device ID.
            band_name: Band name (e.g., "LTE700").
            mgc_ul: Uplink MGC value (0-20 dB).
            mgc_dl: Downlink MGC value (0-20 dB).
        """
        band_info = None
        for b in BANDS:
            if b["name"] == band_name:
                band_info = b
                break
        if not band_info:
            raise HiBoostAPIError(f"Unknown band: {band_name}")

        prefix = band_info["prefix"]
        updates = []

        if mgc_ul is not None:
            if not 0 <= mgc_ul <= 20:
                raise HiBoostAPIError(f"MGC uplink must be 0-20, got {mgc_ul}")
            updates.append({
                "oid": f"{prefix}{OID_MGC_UL}",
                "value": _uint_to_hex(mgc_ul),
                "syntax": "UINT1",
            })

        if mgc_dl is not None:
            if not 0 <= mgc_dl <= 20:
                raise HiBoostAPIError(f"MGC downlink must be 0-20, got {mgc_dl}")
            updates.append({
                "oid": f"{prefix}{OID_MGC_DL}",
                "value": _uint_to_hex(mgc_dl),
                "syntax": "UINT1",
            })

        if not updates:
            raise HiBoostAPIError("No MGC values provided")

        result = self.client.update_device_params(device_id, updates)
        self.clear_cache()
        return {"success": True, "band": band_name, "updates": updates, "result": result}

    def update_rf_switch(self, device_id: str, band_name: str, enabled: bool) -> Dict[str, Any]:
        """Toggle RF switch for a band on/off."""
        band_info = None
        for b in BANDS:
            if b["name"] == band_name:
                band_info = b
                break
        if not band_info:
            raise HiBoostAPIError(f"Unknown band: {band_name}")

        prefix = band_info["prefix"]
        updates = [{
            "oid": f"{prefix}{OID_RF_SWITCH}",
            "value": "01" if enabled else "00",
            "syntax": "UINT1",
        }]

        result = self.client.update_device_params(device_id, updates)
        self.clear_cache()
        return {"success": True, "band": band_name, "rf_switch": enabled, "result": result}

    def _parse_device_detail(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw device detail into structured data."""
        params = raw.get("params", {})
        net = raw.get("netParam", {})

        # Parse IP from hex
        ether_ip_hex = net.get("etherIp", "")
        ip_str = ""
        if ether_ip_hex and len(ether_ip_hex) == 8:
            ip_str = ".".join(str(int(ether_ip_hex[i : i + 2], 16)) for i in range(0, 8, 2))

        # Parse bands
        bands = []
        for band_def in BANDS:
            prefix = band_def["prefix"]
            band = {
                "name": band_def["name"],
                "freq_uplink": band_def["freq_uplink"],
                "freq_downlink": band_def["freq_downlink"],
                "rf_status": _hex_to_uint(params.get(f"{prefix}{OID_RF_STATUS}", "00")) == 0,
                "rf_switch": _hex_to_uint(params.get(f"{prefix}{OID_RF_SWITCH}", "00")) == 1,
                "output_power_ul": _hex_to_sint(params.get(f"{prefix}{OID_OUTPUT_POWER_UL}", "00")),
                "output_power_dl": _hex_to_sint(params.get(f"{prefix}{OID_OUTPUT_POWER_DL}", "00")),
                "mgc_ul": _hex_to_uint(params.get(f"{prefix}{OID_MGC_UL}", "00")),
                "mgc_dl": _hex_to_uint(params.get(f"{prefix}{OID_MGC_DL}", "00")),
                "gain_ul": _hex_to_uint(params.get(f"{prefix}{OID_GAIN_UL}", "00")),
                "gain_dl": _hex_to_uint(params.get(f"{prefix}{OID_GAIN_DL}", "00")),
                "iso_ul": _hex_to_uint(params.get(f"{prefix}{OID_ISO_UL}", "00")) == 0,
                "iso_dl": _hex_to_uint(params.get(f"{prefix}{OID_ISO_DL}", "00")) == 0,
                "overload_ul": _hex_to_uint(params.get(f"{prefix}{OID_OVERLOAD_UL}", "00")) == 0,
                "overload_dl": _hex_to_uint(params.get(f"{prefix}{OID_OVERLOAD_DL}", "00")) == 0,
            }
            bands.append(band)

        # Parse temperature (OID 0203, SINT1)
        temp_hex = params.get("0203", "")
        temperature = _hex_to_sint(temp_hex) if temp_hex else None

        # Connection info
        wifi_ssid = net.get("wifiAp", params.get("0120", ""))
        connection_mode = _hex_to_uint(params.get("0101", "00"))
        # mode: 0=Ethernet, 1=WiFi, 2=Cellular, 3=WiFi+Eth
        mode_names = {0: "Ethernet", 1: "WiFi", 2: "Cellular", 3: "WiFi+Ethernet"}

        return {
            "device_id": raw.get("id", ""),
            "name": raw.get("name", ""),
            "model": raw.get("model", ""),
            "serial_number": raw.get("serialNumber", ""),
            "firmware": raw.get("firmwareVersion", ""),
            "state": raw.get("state", ""),
            "location": raw.get("location", ""),
            "latitude": raw.get("latitude"),
            "longitude": raw.get("longitude"),
            "bands": bands,
            "temperature": temperature,
            "connection": {
                "mode": mode_names.get(connection_mode, f"Unknown({connection_mode})"),
                "wifi_ssid": wifi_ssid,
                "ip": ip_str,
                "online": raw.get("state") == "NORMAL",
            },
            "manufacturer": params.get("0002", "HiBoost"),
            "product": raw.get("modelConfig", {}).get("product", ""),
        }
