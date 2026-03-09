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
        client.get_interfaces.return_value = {
            "interface": [
                {"interface": "lan", "proto": "static"},
                {"interface": "wwan", "proto": "qmi", "up": True},
            ]
        }
        client.get_wireless_status.return_value = {"radio0": {"up": True}}

        service = ChesterService(client)
        status = service.get_router_status()

        assert status["board"]["model"] == "Chester X1"
        assert status["wan"]["interface"] == "wwan"
        assert isinstance(status["interfaces"], list)

    def test_get_cellular_status_detects_qmi(self):
        client = Mock()
        client.get_interfaces.return_value = {
            "interface": [
                {"interface": "wan", "proto": "dhcp"},
                {"interface": "cell0", "proto": "qmi", "up": True},
            ]
        }

        service = ChesterService(client)
        data = service.get_cellular_status()

        assert data["cellular"]["detected"] is True
        assert data["cellular"]["interface"]["proto"] == "qmi"

    def test_get_feature_snapshot(self):
        client = Mock()
        client.get_uci.side_effect = [
            {"values": {"wg0": {"proto": "wireguard"}}},
            {"values": {"rule1": {"target": "TTL"}}},
        ]

        service = ChesterService(client)
        snapshot = service.get_feature_snapshot()

        assert snapshot["features"]["wireguard_present"] is True
        assert snapshot["features"]["ttl_adjustment"] is True
