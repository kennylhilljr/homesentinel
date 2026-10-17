"""
Service layer for Chester 5G Wireless Data Terminal integration.

2026-03-11: Added get_system_info() for full cellular/signal data,
matching the Chester web UI home page fields.
"""

from datetime import datetime
from typing import Any, Dict

from services.chester_client import ChesterClient


class ChesterService:
    """Aggregates router and cellular-relevant status for Chester routers."""

    def __init__(self, client: ChesterClient):
        self.client = client

    def get_router_status(self) -> Dict[str, Any]:
        board = self.client.get_board_info()
        wan = self._safe_call("network", "get_wan")
        wireless = self._safe_call("network", "get_wireless")

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "board": board,
            "wan": wan,
            "wireless": wireless,
        }

    def get_cellular_status(self) -> Dict[str, Any]:
        info = self.client.get_board_info()
        wan = self._safe_call("network", "get_wan")

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cellular": {
                "detected": True,
                "info": info,
                "wan": wan,
            },
        }

    # 2026-03-11: Full system info matching Chester web UI home page
    def get_system_info(self) -> Dict[str, Any]:
        """Get all system and cellular signal info in one call.

        Returns the same fields shown on the Chester web UI status page:
        Device Model, System Version, Hardware Version, IMEI, ICCID,
        IPv4/IPv6 addresses, DNS, Connection Time/Type, CellID, PCID,
        ARFCN, BAND, RSRP, RSRQ, SINR, CA BAND, MCC, MNC.
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            **self.client.get_system_info(),
        }

    def get_lte_band_config(self) -> Dict[str, Any]:
        """Get band lock configuration."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            **self.client.get_lte_band(),
        }

    def get_lte_traffic_stats(self) -> Dict[str, Any]:
        """Get data usage / traffic statistics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            **self.client.get_lte_traffic(),
        }

    def _safe_call(self, module: str, api: str) -> Dict[str, Any]:
        try:
            return self.client.api_call(module, api)
        except Exception:
            return {"error": f"Unable to query {module}.{api}"}
