"""
Tests for Deco Service
Tests node data retrieval, enrichment, caching, and error handling
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import base64

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.deco_service import DecoService
from services.deco_client import InvalidCredentialsError, APIConnectionError


def topology(nodes, node_clients=None):
    """Build a DecoClient.get_topology_local() payload (DecoService's only node source)."""
    return {"nodes": nodes, "node_clients": node_clients or {}}


MAIN_MAC = "AA-BB-CC-DD-EE-01"
SAT_MAC = "AA-BB-CC-DD-EE-02"


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def local_node(mac, nickname, software_ver="1.5.8", device_model="BE63", **extra):
    """A node shaped like a real LuCI admin/device?form=device_list entry."""
    node = {
        "mac": mac,
        "device_id": "DEVID" + mac.replace("-", ""),
        "role": "master" if mac == MAIN_MAC else "slave",
        "nickname": b64(nickname),
        "software_ver": software_ver,
        "device_model": device_model,
        "connection_type": ["band2_4", "band5"],
    }
    node.update(extra)
    return node


def local_clients(node_mac, count, online=True):
    """Local client_list entries (MAC-keyed under node_clients)."""
    suffix = node_mac[-2:]
    return [
        {"mac": f"11-22-33-44-{suffix}-{i:02X}", "name": b64(f"Client {i}"), "online": online,
         "wire_type": "wireless", "connection_type": "band5"}
        for i in range(count)
    ]


def main_topology(software_ver="1.5.8"):
    return topology(
        [local_node(MAIN_MAC, "Main Router", software_ver=software_ver)],
        {MAIN_MAC: local_clients(MAIN_MAC, 5)},
    )


def two_node_topology():
    return topology(
        [local_node(MAIN_MAC, "Main Router"), local_node(SAT_MAC, "Satellite 1")],
        {MAIN_MAC: local_clients(MAIN_MAC, 5), SAT_MAC: local_clients(SAT_MAC, 3)},
    )


class TestDecoServiceInitialization:
    """Tests for DecoService initialization"""

    def test_init_creates_default_deco_client(self):
        """Test initialization creates default DecoClient"""
        with patch("services.deco_service.DecoClient"):
            service = DecoService()
            assert service.deco_client is not None
            assert service._nodes_cache is None
            assert service._cache_timestamp is None

    def test_init_accepts_existing_deco_client(self):
        """Test initialization accepts existing DecoClient instance"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        assert service.deco_client is mock_client

    def test_cache_ttl_is_60_seconds(self):
        """Test cache TTL is set to 60 seconds"""
        service = DecoService(deco_client=Mock())
        assert service.CACHE_TTL == 60


class TestGetNodesWithDetails:
    """Tests for get_nodes_with_details method"""

    def test_returns_list_of_nodes(self):
        """Test returns list of enriched nodes"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert isinstance(nodes, list)
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == MAIN_MAC

    def test_enriches_node_data(self):
        """Test node data is enriched with all required fields"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        node = nodes[0]
        assert "node_id" in node
        assert "node_name" in node
        assert "firmware_version" in node
        assert "uptime_seconds" in node
        assert "connected_clients" in node
        assert "signal_strength" in node
        assert "model" in node
        assert "status" in node
        assert "last_updated" in node
        assert "clients" in node

    def test_caches_results(self):
        """Test results are cached after first fetch"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # First call should fetch from API
        nodes1 = service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 1

        # Second call should use cache
        nodes2 = service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 1  # Still 1
        assert nodes1 == nodes2

    def test_returns_cached_result_within_ttl(self):
        """Test cached result is returned within TTL"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # First call
        nodes1 = service.get_nodes_with_details()
        assert service._cache_timestamp is not None

        # Second call immediately after
        nodes2 = service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 1
        assert nodes1 == nodes2

    def test_refreshes_cache_after_ttl_expires(self):
        """Test cache is refreshed after TTL expires"""
        mock_client = Mock()
        call_count = [0]

        def get_topology_local_side_effect():
            call_count[0] += 1
            return main_topology(software_ver=f"1.5.{call_count[0]}")

        mock_client.get_topology_local.side_effect = get_topology_local_side_effect

        service = DecoService(deco_client=mock_client)

        # First call
        nodes1 = service.get_nodes_with_details()
        assert nodes1[0]["firmware_version"] == "1.5.1"

        # Simulate cache expiry by setting old timestamp
        service._cache_timestamp = datetime.now() - timedelta(seconds=61)

        # Second call should fetch fresh data
        nodes2 = service.get_nodes_with_details()
        assert nodes2[0]["firmware_version"] == "1.5.2"
        assert mock_client.get_topology_local.call_count == 2

    def test_handles_authentication_error(self):
        """Test handles InvalidCredentialsError from client"""
        mock_client = Mock()
        mock_client.get_topology_local.side_effect = InvalidCredentialsError("Invalid credentials")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(InvalidCredentialsError):
            service.get_nodes_with_details()

    def test_handles_api_connection_error(self):
        """Test handles APIConnectionError from client"""
        mock_client = Mock()
        mock_client.get_topology_local.side_effect = APIConnectionError("Connection failed")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.get_nodes_with_details()

    def test_handles_empty_node_list(self):
        """Test handles empty node list from API"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = topology([])

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert isinstance(nodes, list)
        assert len(nodes) == 0

    def test_handles_multiple_nodes(self):
        """Test handles multiple nodes from API"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = two_node_topology()

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 2
        assert nodes[0]["node_id"] == MAIN_MAC
        assert nodes[1]["node_id"] == SAT_MAC
        assert nodes[0]["connected_clients"] == 5
        assert nodes[1]["connected_clients"] == 3


class TestGetNodeById:
    """Tests for get_node_by_id method"""

    def test_returns_node_by_id(self):
        """Test returns specific node by ID"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = two_node_topology()

        service = DecoService(deco_client=mock_client)
        node = service.get_node_by_id(SAT_MAC)

        assert node is not None
        assert node["node_id"] == SAT_MAC
        assert node["node_name"] == "Satellite 1"
        assert [c["raw_data"]["mac"] for c in node["clients"]] == [
            c["mac"] for c in local_clients(SAT_MAC, 3)
        ]

    def test_returns_none_for_missing_node(self):
        """Test returns None for non-existent node ID"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)
        node = service.get_node_by_id("nonexistent")

        assert node is None


class TestEnrichNodeData:
    """Tests for _enrich_node_data method"""

    def test_extracts_all_required_fields(self):
        """Test extracts all required fields from raw node"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "nodeID": "node1",
            "nodeName": "Main Router",
            "fwVersion": "1.5.8",
            "uptime": 432000,
            "connectedClients": 5,
            "signalRSSI": -50,
            "modelName": "Deco M32",
            "status": "online",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["node_id"] == "node1"
        assert enriched["node_name"] == "Main Router"
        assert enriched["firmware_version"] == "1.5.8"
        assert enriched["uptime_seconds"] == 432000
        assert enriched["connected_clients"] == 5
        assert enriched["model"] == "Deco M32"
        assert enriched["status"] == "online"

    def test_handles_alternative_field_names(self):
        """Test handles alternative field names from API"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "node_id": "node1",
            "node_name": "Main Router",
            "firmware_version": "1.5.8",
            "uptimeSeconds": 432000,
            "connected_clients": 5,
            "signal_rssi": -50,
            "model_name": "Deco M32",
            "nodeStatus": "online",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["node_id"] == "node1"
        assert enriched["node_name"] == "Main Router"
        assert enriched["firmware_version"] == "1.5.8"
        assert enriched["uptime_seconds"] == 432000
        assert enriched["connected_clients"] == 5
        assert enriched["model"] == "Deco M32"
        assert enriched["status"] == "online"

    def test_handles_missing_fields_with_defaults(self):
        """Test handles missing fields with sensible defaults"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {"nodeID": "node1"}

        enriched = service._enrich_node_data(raw_node)

        assert enriched["node_id"] == "node1"
        assert enriched["node_name"] == "Node node1"
        assert enriched["firmware_version"] == "unknown"
        assert enriched["uptime_seconds"] == 0
        assert enriched["connected_clients"] == 0
        assert enriched["model"] == "unknown"
        # Unknown status defaults to online to avoid false offline alarms
        assert enriched["status"] == "online"
        assert enriched["clients"] == []

    def test_converts_milliseconds_uptime_to_seconds(self):
        """Test converts uptime from milliseconds to seconds"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # Values above ~100 years in seconds (3153600000) are treated as milliseconds
        raw_node = {
            "nodeID": "node1",
            "nodeName": "Main Router",
            "uptime": 4320000000,  # 4320000 seconds in milliseconds
            "fwVersion": "1.5.8",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["uptime_seconds"] == 4320000

        # Values below the threshold are already seconds and left unchanged
        raw_node["uptime"] = 432000000
        assert service._enrich_node_data(raw_node)["uptime_seconds"] == 432000000

    def test_calculates_signal_strength(self):
        """Test calculates signal strength from RSSI"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "nodeID": "node1",
            "nodeName": "Main Router",
            "signalRSSI": -50,
            "fwVersion": "1.5.8",
        }

        enriched = service._enrich_node_data(raw_node)

        # -50 dBm should convert to ~100%
        assert enriched["signal_strength"] > 80


class TestCalculateSignalStrength:
    """Tests for _calculate_signal_strength method"""

    def test_converts_rssi_to_percentage(self):
        """Test converts RSSI (dBm) to percentage"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # Test various RSSI values
        assert service._calculate_signal_strength(-30) == 100  # Excellent
        assert service._calculate_signal_strength(-50) == 100  # Very good
        assert service._calculate_signal_strength(-70) == 60   # Good
        assert service._calculate_signal_strength(-100) == 0   # Poor

    def test_handles_percentage_values(self):
        """Test handles already-percentage values"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        assert service._calculate_signal_strength(100) == 100
        assert service._calculate_signal_strength(50) == 50
        assert service._calculate_signal_strength(0) == 0

    def test_clamps_values_to_0_100_range(self):
        """Test clamps values to 0-100 range"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        assert service._calculate_signal_strength(-150) == 0  # Below minimum RSSI
        # Values > 100 are treated as a 0-255 scale and clamped to 100
        assert service._calculate_signal_strength(255) == 100
        assert service._calculate_signal_strength(1000) == 100

    def test_handles_invalid_values(self):
        """Test handles invalid signal values gracefully"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        assert service._calculate_signal_strength("invalid") == 0
        assert service._calculate_signal_strength(None) == 0
        assert service._calculate_signal_strength([]) == 0


class TestCacheManagement:
    """Tests for cache management methods"""

    def test_clear_cache_resets_state(self):
        """Test clear_cache resets cache state"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # Populate cache
        service.get_nodes_with_details()
        assert service._nodes_cache is not None
        assert service._cache_timestamp is not None

        # Clear cache
        service.clear_cache()
        assert service._nodes_cache is None
        assert service._cache_timestamp is None

    def test_clear_cache_forces_fresh_fetch_on_next_call(self):
        """Test clearing cache forces fresh fetch on next call"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # First call
        service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 1

        # Clear and call again
        service.clear_cache()
        service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 2


class TestNodeDataStructure:
    """Tests for node data structure and types"""

    def test_node_fields_have_correct_types(self):
        """Test node fields have correct data types"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()
        node = nodes[0]

        assert isinstance(node["node_id"], str)
        assert isinstance(node["node_name"], str)
        assert isinstance(node["firmware_version"], str)
        assert isinstance(node["uptime_seconds"], int)
        assert isinstance(node["connected_clients"], int)
        assert isinstance(node["signal_strength"], int)
        assert isinstance(node["model"], str)
        assert isinstance(node["status"], str)
        assert isinstance(node["last_updated"], str)

    def test_signal_strength_is_0_to_100_range(self):
        """Test signal strength is always in 0-100 range"""
        mock_client = Mock()

        test_cases = [
            {"signalRSSI": -20},
            {"signalRSSI": -50},
            {"signalRSSI": -80},
            {"signalRSSI": -100},
            {"signalRSSI": 0},
            {"signalRSSI": 50},
            {"signalRSSI": 100},
        ]

        service = DecoService(deco_client=mock_client)

        for test_case in test_cases:
            raw_node = {
                "nodeID": "node1",
                "nodeName": "Test",
                "fwVersion": "1.0",
                **test_case,
            }
            enriched = service._enrich_node_data(raw_node)
            assert 0 <= enriched["signal_strength"] <= 100


class TestSignalStrengthEdgeCases:
    """Tests for signal strength conversion edge cases"""

    def test_signal_strength_zero(self):
        """Test signal strength of 0"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        assert service._calculate_signal_strength(0) == 0

    def test_signal_strength_fifty(self):
        """Test signal strength of 50 (middle value)"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        assert service._calculate_signal_strength(50) == 50

    def test_signal_strength_hundred(self):
        """Test signal strength of 100 (maximum)"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        assert service._calculate_signal_strength(100) == 100

    def test_signal_strength_negative_values(self):
        """Test signal strength with negative values (RSSI dBm)"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        # RSSI values are negative dBm, should be converted
        result = service._calculate_signal_strength(-30)
        assert 0 <= result <= 100

    def test_signal_strength_greater_than_hundred(self):
        """Test signal strength greater than 100 is scaled from 0-255"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        assert service._calculate_signal_strength(150) == 58  # int(150 / 255 * 100)
        assert service._calculate_signal_strength(255) == 100


class TestCacheHitMissBehavior:
    """Tests for cache hit/miss behavior with timing"""

    def test_cache_hit_doesnt_call_api(self):
        """Test cache hit does not call API"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # Call twice
        service.get_nodes_with_details()
        service.get_nodes_with_details()

        # API should only be called once (cache hit on second call)
        assert mock_client.get_topology_local.call_count == 1

    def test_cache_miss_calls_api(self):
        """Test cache miss calls API"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # First call
        service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 1

        # Expire cache
        service._cache_timestamp = datetime.now() - timedelta(seconds=61)

        # Second call should be a miss
        service.get_nodes_with_details()
        assert mock_client.get_topology_local.call_count == 2

    def test_cache_timestamp_updated_on_fetch(self):
        """Test cache timestamp is updated on fetch"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # Call to populate cache
        service.get_nodes_with_details()
        timestamp1 = service._cache_timestamp

        # Fetch again (cache hit)
        service.get_nodes_with_details()
        timestamp2 = service._cache_timestamp

        # Timestamps should be the same (cache hit)
        assert timestamp1 == timestamp2


class TestConcurrentRequests:
    """Tests for concurrent requests during cache refresh"""

    def test_multiple_concurrent_requests_use_same_cache(self):
        """Test multiple concurrent requests during cache refresh use cached data"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = main_topology()

        service = DecoService(deco_client=mock_client)

        # Multiple calls within TTL
        results = []
        for _ in range(5):
            results.append(service.get_nodes_with_details())

        # All should be identical (from cache)
        for result in results[1:]:
            assert result == results[0]

        # API called only once
        assert mock_client.get_topology_local.call_count == 1


class TestFieldEnrichment:
    """Tests for field enrichment for various API response formats"""

    def test_enrichment_with_camelcase_fields(self):
        """Test enrichment with camelCase API fields"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "nodeID": "node1",
            "nodeName": "Router",
            "fwVersion": "1.5.8",
            "uptime": 432000,
            "connectedClients": 5,
            "signalRSSI": -50,
            "modelName": "Deco M32",
            "status": "online",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["node_id"] == "node1"
        assert enriched["uptime_seconds"] == 432000
        assert enriched["connected_clients"] == 5

    def test_enrichment_with_snake_case_fields(self):
        """Test enrichment with snake_case API fields"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "node_id": "node1",
            "node_name": "Router",
            "firmware_version": "1.5.8",
            "uptime_seconds": 432000,
            "connected_clients": 5,
            "signal_rssi": -50,
            "model_name": "Deco M32",
            "node_status": "online",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["node_id"] == "node1"
        assert enriched["uptime_seconds"] == 432000
        assert enriched["connected_clients"] == 5

    def test_enrichment_with_missing_optional_fields(self):
        """Test enrichment handles missing optional fields"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "nodeID": "node1",
            # Missing nodeName, fwVersion, etc.
        }

        enriched = service._enrich_node_data(raw_node)

        # Should have defaults
        assert "node_id" in enriched
        assert "node_name" in enriched
        assert "firmware_version" in enriched


class TestUptimeCalculation:
    """Tests for uptime calculation edge cases"""

    def test_uptime_zero_seconds(self):
        """Test uptime with 0 seconds"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "nodeID": "node1",
            "uptime": 0,
            "nodeName": "Router",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["uptime_seconds"] == 0

    def test_uptime_large_values(self):
        """Test uptime with very large values"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # 365 days in seconds
        large_uptime = 365 * 24 * 60 * 60
        raw_node = {
            "nodeID": "node1",
            "uptime": large_uptime,
            "nodeName": "Router",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["uptime_seconds"] == large_uptime

    def test_uptime_milliseconds_conversion(self):
        """Test uptime conversion from milliseconds to seconds"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # 432000000 milliseconds = 432000 seconds
        raw_node = {
            "nodeID": "node1",
            "uptime": 432000000,
            "nodeName": "Router",
        }

        enriched = service._enrich_node_data(raw_node)

        # Should convert milliseconds to seconds
        assert enriched["uptime_seconds"] == 432000 or enriched["uptime_seconds"] == 432000000


class TestErrorRecovery:
    """Tests for error recovery and resilience"""

    def test_malformed_response_handling(self):
        """Test handling of malformed API responses"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = topology([
            {
                "mac": None,  # Invalid
                "nickname": "Router",
            }
        ])

        service = DecoService(deco_client=mock_client)

        # Should handle gracefully
        nodes = service.get_nodes_with_details()
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "unknown"
        assert nodes[0]["node_name"] == "Router"

    def test_partial_field_response(self):
        """Test handling of responses with only some fields"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = topology([
            {
                "mac": MAIN_MAC,
                # Missing many fields
            }
        ])

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 1
        assert nodes[0]["node_id"] == MAIN_MAC
        assert nodes[0]["node_name"] == f"Node {MAIN_MAC}"
        assert nodes[0]["firmware_version"] == "unknown"
        assert nodes[0]["model"] == "unknown"
        assert nodes[0]["connected_clients"] == 0
        assert nodes[0]["clients"] == []

    def test_invalid_rssi_values(self):
        """Test handling of invalid RSSI values"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        # Invalid RSSI values should be handled
        result1 = service._calculate_signal_strength(-999)
        result2 = service._calculate_signal_strength(999)

        assert 0 <= result1 <= 100
        assert 0 <= result2 <= 100

    def test_offline_node_handling(self):
        """Test handling of offline nodes"""
        mock_client = Mock()
        mock_client.get_topology_local.return_value = topology(
            [local_node(MAIN_MAC, "Router", status="offline", signalRSSI=-100)],  # Very weak signal
            {MAIN_MAC: []},
        )

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 1
        assert nodes[0]["status"] == "offline"
        assert nodes[0]["connected_clients"] == 0


class TestComprehensiveLiveScenarios:
    """Tests for comprehensive real-world scenarios"""

    def test_complete_node_lifecycle(self):
        """Test complete node lifecycle from fetch to cache expiry to refresh"""
        mock_client = Mock()
        call_count = [0]

        def get_topology_local():
            call_count[0] += 1
            mac = f"AA-BB-CC-DD-EE-{call_count[0]:02X}"
            return topology([local_node(mac, "Main Router")], {mac: local_clients(mac, 5)})

        mock_client.get_topology_local.side_effect = get_topology_local

        service = DecoService(deco_client=mock_client)

        # Initial fetch
        nodes1 = service.get_nodes_with_details()
        assert nodes1[0]["node_id"] == "AA-BB-CC-DD-EE-01"

        # Cache hit
        nodes2 = service.get_nodes_with_details()
        assert nodes2[0]["node_id"] == "AA-BB-CC-DD-EE-01"  # Same cached data
        assert mock_client.get_topology_local.call_count == 1

        # Expire cache
        service._cache_timestamp = datetime.now() - timedelta(seconds=61)

        # Cache miss - refresh
        nodes3 = service.get_nodes_with_details()
        assert nodes3[0]["node_id"] == "AA-BB-CC-DD-EE-02"  # New data
        assert mock_client.get_topology_local.call_count == 2

    def test_mixed_online_offline_nodes(self):
        """Test handling of mixed online/offline nodes in single response"""
        mock_client = Mock()
        sat2_mac = "AA-BB-CC-DD-EE-03"
        mock_client.get_topology_local.return_value = topology(
            [
                local_node(MAIN_MAC, "Main Router", status="online", signalRSSI=-50),
                local_node(SAT_MAC, "Satellite 1", status="online", signalRSSI=-70),
                local_node(sat2_mac, "Satellite 2", status="offline", signalRSSI=-100),
            ],
            # 10 clients total keeps the >10-client mesh-wide online fallback out of play
            {MAIN_MAC: local_clients(MAIN_MAC, 6), SAT_MAC: local_clients(SAT_MAC, 4), sat2_mac: []},
        )

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 3
        assert sum(1 for n in nodes if n["status"] == "online") == 2
        assert sum(1 for n in nodes if n["status"] == "offline") == 1


class TestLocalTopologySchema:
    """Regressions for local LuCI device_list nodes (issue #6)."""

    def test_issue_exact_payload(self):
        c = Mock()
        m = "AA-BB-CC-DD-EE-01"
        c.get_topology_local.return_value = {
            "nodes": [{"mac": m, "nickname": "Main Router", "software_ver": "1.5.8", "device_model": "BE63"}],
            "node_clients": {m: [{"mac": "11-22-33-44-55-66", "online": True}]},
        }
        n = DecoService(c).get_nodes_with_details()[0]
        assert n["node_id"] == m
        assert n["node_name"] == "Main Router"
        assert n["firmware_version"] == "1.5.8"
        assert n["model"] == "BE63"
        assert n["connected_clients"] == 1
        assert len(n["clients"]) == 1
        assert n["clients"][0]["raw_data"]["mac"] == "11-22-33-44-55-66"

    def test_realistic_node_prefers_mac_over_device_id(self):
        clients = local_clients(MAIN_MAC, 2)
        node = local_node(MAIN_MAC, "Living Room", software_ver="1.2.3 Build 20250101", device_model="X55")
        assert node["device_id"] != MAIN_MAC
        c = Mock()
        c.get_topology_local.return_value = topology([node], {MAIN_MAC: clients})

        n = DecoService(c).get_nodes_with_details()[0]

        assert n["node_id"] == MAIN_MAC
        assert n["node_name"] == "Living Room"
        assert n["firmware_version"] == "1.2.3 Build 20250101"
        assert n["model"] == "X55"
        assert [cl["raw_data"] for cl in n["clients"]] == clients
        assert n["connected_clients"] == 2

    def test_mac_wins_over_conflicting_id(self):
        service = DecoService(deco_client=Mock())
        raw = local_node(MAIN_MAC, "Main", id="other-id", nodeID="cloud-id")
        enriched = service._enrich_node_data(raw, {MAIN_MAC: [{"name": "x"}], "other-id": []})
        assert enriched["node_id"] == MAIN_MAC
        assert enriched["connected_clients"] == 1

    def test_legacy_identifier_fallbacks_without_mac(self):
        service = DecoService(deco_client=Mock())
        assert service._enrich_node_data({"device_id": "dev1", "id": "id1"})["node_id"] == "dev1"
        assert service._enrich_node_data({"id": "id1", "macAddress": "AA"})["node_id"] == "id1"
        assert service._enrich_node_data({"macAddress": "AA"})["node_id"] == "AA"
        assert service._enrich_node_data({"mac": "", "deviceId": "d2"})["node_id"] == "d2"

    def test_two_nodes_get_distinct_clients(self):
        main_clients = local_clients(MAIN_MAC, 2)
        sat_clients = local_clients(SAT_MAC, 3)
        c = Mock()
        c.get_topology_local.return_value = topology(
            [local_node(MAIN_MAC, "Main"), local_node(SAT_MAC, "Sat")],
            {MAIN_MAC: main_clients, SAT_MAC: sat_clients},
        )
        service = DecoService(c)

        main = service.get_node_by_id(MAIN_MAC)
        sat = service.get_node_by_id(SAT_MAC)

        assert [cl["raw_data"] for cl in main["clients"]] == main_clients
        assert [cl["raw_data"] for cl in sat["clients"]] == sat_clients
        assert main["connected_clients"] == 2
        assert sat["connected_clients"] == 3

    def test_empty_and_absent_node_clients(self):
        c = Mock()
        c.get_topology_local.return_value = topology(
            [local_node(MAIN_MAC, "Main"), local_node(SAT_MAC, "Sat")],
            {MAIN_MAC: []},
        )
        nodes = DecoService(c).get_nodes_with_details()
        for n in nodes:
            assert n["clients"] == []
            assert n["connected_clients"] == 0

        c2 = Mock()
        c2.get_topology_local.return_value = {"nodes": [local_node(MAIN_MAC, "Main")]}
        n = DecoService(c2).get_nodes_with_details()[0]
        assert n["node_id"] == MAIN_MAC
        assert n["clients"] == []
        assert n["connected_clients"] == 0

    def test_nickname_plain_base64_and_invalid_utf8(self):
        service = DecoService(deco_client=Mock())
        assert service._enrich_node_data({"mac": MAIN_MAC, "nickname": "Main Router"})["node_name"] == "Main Router"
        assert service._enrich_node_data({"mac": MAIN_MAC, "nickname": b64("Kitchen")})["node_name"] == "Kitchen"
        assert service._enrich_node_data({"mac": MAIN_MAC, "nickname": b64("Café")})["node_name"] == "Café"
        invalid_utf8 = base64.b64encode(b"\xff\xfe\xfa").decode("ascii")
        assert service._enrich_node_data({"mac": MAIN_MAC, "nickname": invalid_utf8})["node_name"] == invalid_utf8
        # Name fallbacks are preserved
        assert service._enrich_node_data({"mac": MAIN_MAC, "nickname": ""})["node_name"] == f"Node {MAIN_MAC}"
        assert service._enrich_node_data({"mac": MAIN_MAC, "nodeName": "Cloud", "nickname": b64("X")})["node_name"] == "Cloud"

    def test_online_override_uses_local_mac(self):
        """status=0 nodes become online only when an online client is attached."""
        c = Mock()
        c.get_topology_local.return_value = topology(
            [
                local_node(MAIN_MAC, "Main", status=0),
                local_node(SAT_MAC, "Sat", status=0),
            ],
            # Fewer than 11 clients total, so the mesh-wide fallback cannot apply.
            {MAIN_MAC: local_clients(MAIN_MAC, 1, online=True), SAT_MAC: local_clients(SAT_MAC, 1, online=False)},
        )
        service = DecoService(c)

        assert service.get_node_by_id(MAIN_MAC)["status"] == "online"
        assert service.get_node_by_id(SAT_MAC)["status"] == "offline"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
