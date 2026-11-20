"""Tests for Chester service layer."""

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chester_service import ChesterService


class TestChesterService:
    def test_get_router_status(self):
        client = Mock()
        client.get_board_info.return_value = {"model": "Chester X1"}

        def api_call(module, api):
            if (module, api) == ("network", "get_wan"):
                return {"interface": "wwan", "proto": "qmi", "up": True}
            if (module, api) == ("network", "get_wireless"):
                return {"radio0": {"up": True}}
            raise AssertionError(f"unexpected call {module}.{api}")

        client.api_call.side_effect = api_call

        service = ChesterService(client)
        status = service.get_router_status()

        assert status["board"]["model"] == "Chester X1"
        assert status["wan"]["interface"] == "wwan"
        assert status["wireless"]["radio0"]["up"] is True
        assert "timestamp" in status

    def test_get_router_status_wan_error_fallback(self):
        client = Mock()
        client.get_board_info.return_value = {"model": "Chester X1"}
        client.api_call.side_effect = RuntimeError("boom")

        status = ChesterService(client).get_router_status()

        assert status["wan"] == {"error": "Unable to query network.get_wan"}
        assert status["wireless"] == {"error": "Unable to query network.get_wireless"}

    def test_get_cellular_status_passes_through_board_info_and_wan(self):
        # QMI/protocol detection was removed: the service always reports
        # detected=True and passes board info and WAN data through.
        client = Mock()
        client.get_board_info.return_value = {"model": "Chester X1"}
        client.api_call.return_value = {"interface": "cell0", "proto": "qmi", "up": True}

        service = ChesterService(client)
        data = service.get_cellular_status()

        assert data["cellular"]["detected"] is True
        assert data["cellular"]["info"]["model"] == "Chester X1"
        assert data["cellular"]["wan"]["proto"] == "qmi"
        client.api_call.assert_called_once_with("network", "get_wan")

    def test_get_system_info_merges_client_data(self):
        client = Mock()
        client.get_system_info.return_value = {"imei": "123", "rsrp": -95}

        info = ChesterService(client).get_system_info()

        assert info["imei"] == "123"
        assert info["rsrp"] == -95
        assert "timestamp" in info
