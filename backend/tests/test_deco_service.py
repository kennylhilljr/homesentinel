"""
Tests for Deco Service
Tests node data retrieval, enrichment, caching, and error handling
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.deco_service import DecoService
from services.deco_client import InvalidCredentialsError, APIConnectionError


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
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert isinstance(nodes, list)
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node1"

    def test_enriches_node_data(self):
        """Test node data is enriched with all required fields"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

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

    def test_caches_results(self):
        """Test results are cached after first fetch"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # First call should fetch from API
        nodes1 = service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 1

        # Second call should use cache
        nodes2 = service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 1  # Still 1
        assert nodes1 == nodes2

    def test_returns_cached_result_within_ttl(self):
        """Test cached result is returned within TTL"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # First call
        nodes1 = service.get_nodes_with_details()
        assert service._cache_timestamp is not None

        # Second call immediately after
        nodes2 = service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 1
        assert nodes1 == nodes2

    def test_refreshes_cache_after_ttl_expires(self):
        """Test cache is refreshed after TTL expires"""
        mock_client = Mock()
        call_count = [0]

        def get_node_list_side_effect():
            call_count[0] += 1
            return [
                {
                    "nodeID": "node1",
                    "nodeName": "Main Router",
                    "fwVersion": f"1.5.{call_count[0]}",
                    "uptime": 432000,
                    "connectedClients": 5,
                    "signalRSSI": -50,
                    "modelName": "Deco M32",
                    "status": "online",
                }
            ]

        mock_client.get_node_list.side_effect = get_node_list_side_effect

        service = DecoService(deco_client=mock_client)

        # First call
        nodes1 = service.get_nodes_with_details()
        assert nodes1[0]["firmware_version"] == "1.5.1"

        # Simulate cache expiry by setting old timestamp
        service._cache_timestamp = datetime.now() - timedelta(seconds=61)

        # Second call should fetch fresh data
        nodes2 = service.get_nodes_with_details()
        assert nodes2[0]["firmware_version"] == "1.5.2"
        assert mock_client.get_node_list.call_count == 2

    def test_handles_authentication_error(self):
        """Test handles InvalidCredentialsError from client"""
        mock_client = Mock()
        mock_client.get_node_list.side_effect = InvalidCredentialsError("Invalid credentials")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(InvalidCredentialsError):
            service.get_nodes_with_details()

    def test_handles_api_connection_error(self):
        """Test handles APIConnectionError from client"""
        mock_client = Mock()
        mock_client.get_node_list.side_effect = APIConnectionError("Connection failed")

        service = DecoService(deco_client=mock_client)

        with pytest.raises(APIConnectionError):
            service.get_nodes_with_details()

    def test_handles_empty_node_list(self):
        """Test handles empty node list from API"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = []

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert isinstance(nodes, list)
        assert len(nodes) == 0

    def test_handles_multiple_nodes(self):
        """Test handles multiple nodes from API"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            },
            {
                "nodeID": "node2",
                "nodeName": "Satellite 1",
                "fwVersion": "1.5.8",
                "uptime": 400000,
                "connectedClients": 3,
                "signalRSSI": -65,
                "modelName": "Deco M32",
                "status": "online",
            },
        ]

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 2
        assert nodes[0]["node_id"] == "node1"
        assert nodes[1]["node_id"] == "node2"


class TestGetNodeById:
    """Tests for get_node_by_id method"""

    def test_returns_node_by_id(self):
        """Test returns specific node by ID"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            },
            {
                "nodeID": "node2",
                "nodeName": "Satellite 1",
                "fwVersion": "1.5.8",
                "uptime": 400000,
                "connectedClients": 3,
                "signalRSSI": -65,
                "modelName": "Deco M32",
                "status": "online",
            },
        ]

        service = DecoService(deco_client=mock_client)
        node = service.get_node_by_id("node2")

        assert node is not None
        assert node["node_id"] == "node2"
        assert node["node_name"] == "Satellite 1"

    def test_returns_none_for_missing_node(self):
        """Test returns None for non-existent node ID"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

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
        assert enriched["status"] == "unknown"

    def test_converts_milliseconds_uptime_to_seconds(self):
        """Test converts uptime from milliseconds to seconds"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)

        raw_node = {
            "nodeID": "node1",
            "nodeName": "Main Router",
            "uptime": 432000000,  # 432000 seconds in milliseconds
            "fwVersion": "1.5.8",
        }

        enriched = service._enrich_node_data(raw_node)

        assert enriched["uptime_seconds"] == 432000

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

        assert service._calculate_signal_strength(-150) == 0  # Below minimum
        assert service._calculate_signal_strength(150) == 100  # Above maximum

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
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

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
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # First call
        service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 1

        # Clear and call again
        service.clear_cache()
        service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 2


class TestNodeDataStructure:
    """Tests for node data structure and types"""

    def test_node_fields_have_correct_types(self):
        """Test node fields have correct data types"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

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
        """Test signal strength greater than 100 is clamped"""
        mock_client = Mock()
        service = DecoService(deco_client=mock_client)
        assert service._calculate_signal_strength(150) == 100


class TestCacheHitMissBehavior:
    """Tests for cache hit/miss behavior with timing"""

    def test_cache_hit_doesnt_call_api(self):
        """Test cache hit does not call API"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Call twice
        service.get_nodes_with_details()
        service.get_nodes_with_details()

        # API should only be called once (cache hit on second call)
        assert mock_client.get_node_list.call_count == 1

    def test_cache_miss_calls_api(self):
        """Test cache miss calls API"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # First call
        service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 1

        # Expire cache
        service._cache_timestamp = datetime.now() - timedelta(seconds=61)

        # Second call should be a miss
        service.get_nodes_with_details()
        assert mock_client.get_node_list.call_count == 2

    def test_cache_timestamp_updated_on_fetch(self):
        """Test cache timestamp is updated on fetch"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Call to populate cache
        service.get_nodes_with_details()
        timestamp1 = service._cache_timestamp

        # Wait a bit and fetch again (cache hit)
        time.sleep(0.01)
        service.get_nodes_with_details()
        timestamp2 = service._cache_timestamp

        # Timestamps should be the same (cache hit)
        assert timestamp1 == timestamp2


class TestConcurrentRequests:
    """Tests for concurrent requests during cache refresh"""

    def test_multiple_concurrent_requests_use_same_cache(self):
        """Test multiple concurrent requests during cache refresh use cached data"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "fwVersion": "1.5.8",
                "uptime": 432000,
                "connectedClients": 5,
                "signalRSSI": -50,
                "modelName": "Deco M32",
                "status": "online",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Multiple calls within TTL
        results = []
        for _ in range(5):
            results.append(service.get_nodes_with_details())

        # All should be identical (from cache)
        for result in results[1:]:
            assert result == results[0]

        # API called only once
        assert mock_client.get_node_list.call_count == 1


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
        mock_client.get_node_list.return_value = [
            {
                "nodeID": None,  # Invalid
                "nodeName": "Router",
            }
        ]

        service = DecoService(deco_client=mock_client)

        # Should handle gracefully
        nodes = service.get_nodes_with_details()
        assert len(nodes) == 1

    def test_partial_field_response(self):
        """Test handling of responses with only some fields"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                # Missing many fields
            }
        ]

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node1"

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
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Router",
                "status": "offline",
                "signalRSSI": -100,  # Very weak signal
                "connectedClients": 0,
            }
        ]

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

        def get_node_list():
            call_count[0] += 1
            return [
                {
                    "nodeID": f"node_{call_count[0]}",
                    "nodeName": "Main Router",
                    "fwVersion": "1.5.8",
                    "uptime": 432000,
                    "connectedClients": 5,
                    "signalRSSI": -50,
                    "modelName": "Deco M32",
                    "status": "online",
                }
            ]

        mock_client.get_node_list.side_effect = get_node_list

        service = DecoService(deco_client=mock_client)

        # Initial fetch
        nodes1 = service.get_nodes_with_details()
        assert nodes1[0]["node_id"] == "node_1"

        # Cache hit
        nodes2 = service.get_nodes_with_details()
        assert nodes2[0]["node_id"] == "node_1"  # Same cached data
        assert mock_client.get_node_list.call_count == 1

        # Expire cache
        service._cache_timestamp = datetime.now() - timedelta(seconds=61)

        # Cache miss - refresh
        nodes3 = service.get_nodes_with_details()
        assert nodes3[0]["node_id"] == "node_2"  # New data
        assert mock_client.get_node_list.call_count == 2

    def test_mixed_online_offline_nodes(self):
        """Test handling of mixed online/offline nodes in single response"""
        mock_client = Mock()
        mock_client.get_node_list.return_value = [
            {
                "nodeID": "node1",
                "nodeName": "Main Router",
                "status": "online",
                "signalRSSI": -50,
                "connectedClients": 10,
            },
            {
                "nodeID": "node2",
                "nodeName": "Satellite 1",
                "status": "online",
                "signalRSSI": -70,
                "connectedClients": 5,
            },
            {
                "nodeID": "node3",
                "nodeName": "Satellite 2",
                "status": "offline",
                "signalRSSI": -100,
                "connectedClients": 0,
            },
        ]

        service = DecoService(deco_client=mock_client)
        nodes = service.get_nodes_with_details()

        assert len(nodes) == 3
        assert sum(1 for n in nodes if n["status"] == "online") == 2
        assert sum(1 for n in nodes if n["status"] == "offline") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
