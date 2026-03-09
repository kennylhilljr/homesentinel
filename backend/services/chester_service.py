"""
Service layer for Chester 5G Wireless Data Terminal integration.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

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

    def _safe_call(self, module: str, api: str) -> Dict[str, Any]:
        try:
            return self.client.api_call(module, api)
        except Exception:
            return {"error": f"Unable to query {module}.{api}"}
