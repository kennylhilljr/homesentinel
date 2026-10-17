"""
Test suite for Deco topology endpoint
Tests the /api/deco/topology endpoint functionality
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from routes.deco import router, set_deco_service, set_correlation_service
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Create a test app with the Deco router
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestTopologyEndpoint:
    """Test cases for the topology endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        # Mock Deco service
        self.mock_deco_service = Mock()
        self.mock_deco_service.get_nodes_with_details.return_value = [
            {
                "node_id": "node_1",
                "node_name": "Main Node",
                "firmware_version": "1.5.0",
                "status": "online",
                "signal_strength": 85,
                "connected_clients": 3,
                "uptime_seconds": 86400,
                "model": "Deco M70",
                "last_updated": datetime.now().isoformat(),
                "raw_data": {
                    "nodeID": "node_1",
                    "macAddress": "AA:BB:CC:DD:EE:01",
                    "nodeName": "Main Node",
                },
            },
            {
                "node_id": "node_2",
                "node_name": "Bedroom Node",
                "firmware_version": "1.5.0",
                "status": "online",
                "signal_strength": 72,
                "connected_clients": 2,
                "uptime_seconds": 43200,
                "model": "Deco M70",
                "last_updated": datetime.now().isoformat(),
                "raw_data": {
                    "nodeID": "node_2",
                    "macAddress": "AA:BB:CC:DD:EE:02",
                    "nodeName": "Bedroom Node",
                },
            },
        ]
        self.mock_deco_service.deco_client = Mock()
        self.mock_deco_service.deco_client.get_client_list.return_value = [
            {
                "macAddress": "11:22:33:44:55:66",
                "nodeID": "node_1",
                "clientName": "iPhone",
                "name": "iPhone",
                "ipAddress": "192.168.1.10",
            },
            {
                "macAddress": "11:22:33:44:55:77",
                "nodeID": "node_1",
                "clientName": "Laptop",
                "name": "Laptop",
                "ipAddress": "192.168.1.11",
            },
            {
                "macAddress": "11:22:33:44:55:88",
                "nodeID": "node_2",
                "clientName": "Smart TV",
                "name": "Smart TV",
                "ipAddress": "192.168.1.12",
            },
        ]

        # Mock correlation service
        self.mock_correlation_service = Mock()
        self.mock_correlation_service.get_merged_clients.return_value = {
            "merged_devices": [
                {
                    "device_id": "device_1",
                    "mac_address": "11:22:33:44:55:66",
                    "current_ip": "192.168.1.10",
                    "deco_client_name": "iPhone",
                    "vendor_name": "APPLE",
                    "friendly_name": "John's iPhone",
                    "status": "online",
                    "first_seen": "2026-03-01T10:00:00Z",
                    "last_seen": "2026-03-06T23:00:00Z",
                },
                {
                    "device_id": "device_2",
                    "mac_address": "11:22:33:44:55:77",
                    "current_ip": "192.168.1.11",
                    "deco_client_name": "Laptop",
                    "vendor_name": "DELL",
                    "friendly_name": "Work Laptop",
                    "status": "online",
                    "first_seen": "2026-03-01T10:00:00Z",
                    "last_seen": "2026-03-06T23:00:00Z",
                },
                {
                    "device_id": "device_3",
                    "mac_address": "11:22:33:44:55:88",
                    "current_ip": "192.168.1.12",
                    "deco_client_name": "Smart TV",
                    "vendor_name": "SAMSUNG",
                    "friendly_name": "Living Room TV",
                    "status": "online",
                    "first_seen": "2026-03-01T10:00:00Z",
                    "last_seen": "2026-03-06T23:00:00Z",
                },
            ],
            "total_merged": 3,
            "unmatched_deco_clients": [],
            "unmatched_deco_count": 0,
            "unmatched_lan_devices": 0,
            "timestamp": datetime.now().isoformat(),
            "correlation_stats": {
                "total_deco_clients": 3,
                "total_lan_devices": 3,
                "total_merged": 3,
                "correlation_percentage": 100.0,
            },
        }

        # Set the mocked services
        set_deco_service(self.mock_deco_service)
        set_correlation_service(self.mock_correlation_service)

    def test_topology_endpoint_success(self):
        """Test successful topology endpoint response"""
        response = client.get("/api/deco/topology")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "nodes" in data
        assert "devices" in data
        assert "relationships" in data
        assert "total_nodes" in data
        assert "total_devices" in data
        assert "total_relationships" in data
        assert "timestamp" in data

    def test_topology_nodes_structure(self):
        """Test topology nodes have correct structure"""
        response = client.get("/api/deco/topology")
        data = response.json()
        nodes = data["nodes"]

        assert len(nodes) == 2
        assert nodes[0]["node_id"] == "node_1"
        assert nodes[0]["node_name"] == "Main Node"
        assert nodes[0]["status"] == "online"
        assert "signal_strength" in nodes[0]
        assert "connected_clients" in nodes[0]
        assert "mac_address" in nodes[0]

    def test_topology_devices_structure(self):
        """Test topology devices have correct structure"""
        response = client.get("/api/deco/topology")
        data = response.json()
        devices = data["devices"]

        assert len(devices) == 3
        assert devices[0]["device_id"] == "device_1"
        assert devices[0]["mac_address"] == "11:22:33:44:55:66"
        assert devices[0]["device_name"] == "iPhone"
        assert devices[0]["status"] == "online"
        assert "friendly_name" in devices[0]
        assert "vendor_name" in devices[0]

    def test_topology_relationships_structure(self):
        """Test topology relationships have correct structure"""
        response = client.get("/api/deco/topology")
        data = response.json()
        relationships = data["relationships"]

        assert len(relationships) == 3

        # Check first relationship
        rel = relationships[0]
        assert "device_id" in rel
        assert "device_mac" in rel
        assert "node_id" in rel
        assert "node_mac" in rel

    def test_topology_counts(self):
        """Test topology counts are accurate"""
        response = client.get("/api/deco/topology")
        data = response.json()

        assert data["total_nodes"] == 2
        assert data["total_devices"] == 3
        assert data["total_relationships"] == 3

    def test_topology_device_node_associations(self):
        """Test that devices are correctly associated with nodes"""
        response = client.get("/api/deco/topology")
        data = response.json()
        relationships = data["relationships"]

        # Find relationships for node_1
        node_1_rels = [r for r in relationships if r["node_id"] == "node_1"]
        assert len(node_1_rels) == 2

        # Find relationships for node_2
        node_2_rels = [r for r in relationships if r["node_id"] == "node_2"]
        assert len(node_2_rels) == 1

    def test_topology_services_not_initialized(self):
        """Test error when services are not initialized"""
        set_deco_service(None)
        set_correlation_service(None)

        response = client.get("/api/deco/topology")

        assert response.status_code == 500
        data = response.json()
        assert "Services not initialized" in data.get("detail", "")

        # Re-initialize services
        set_deco_service(self.mock_deco_service)
        set_correlation_service(self.mock_correlation_service)

    def test_topology_with_offline_nodes(self):
        """Test topology with offline nodes"""
        # Update mock to include offline node
        self.mock_deco_service.get_nodes_with_details.return_value = [
            {
                "node_id": "node_1",
                "node_name": "Main Node",
                "status": "online",
                "signal_strength": 85,
                "connected_clients": 2,
                "firmware_version": "1.5.0",
                "uptime_seconds": 86400,
                "model": "Deco M70",
                "last_updated": datetime.now().isoformat(),
                "raw_data": {"macAddress": "AA:BB:CC:DD:EE:01"},
            },
            {
                "node_id": "node_3",
                "node_name": "Offline Node",
                "status": "offline",
                "signal_strength": 0,
                "connected_clients": 0,
                "firmware_version": "1.5.0",
                "uptime_seconds": 0,
                "model": "Deco M70",
                "last_updated": datetime.now().isoformat(),
                "raw_data": {"macAddress": "AA:BB:CC:DD:EE:03"},
            },
        ]

        response = client.get("/api/deco/topology")
        data = response.json()
        nodes = data["nodes"]

        # Check that offline node is included
        offline_nodes = [n for n in nodes if n["status"] == "offline"]
        assert len(offline_nodes) == 1
        assert offline_nodes[0]["node_name"] == "Offline Node"

    def test_topology_with_offline_devices(self):
        """Test topology with offline devices"""
        # Update mock to include offline device
        self.mock_correlation_service.get_merged_clients.return_value = {
            "merged_devices": [
                {
                    "device_id": "device_1",
                    "mac_address": "11:22:33:44:55:66",
                    "current_ip": "192.168.1.10",
                    "deco_client_name": "iPhone",
                    "vendor_name": "APPLE",
                    "friendly_name": "John's iPhone",
                    "status": "online",
                    "first_seen": "2026-03-01T10:00:00Z",
                    "last_seen": "2026-03-06T23:00:00Z",
                },
                {
                    "device_id": "device_4",
                    "mac_address": "11:22:33:44:55:99",
                    "current_ip": "",
                    "deco_client_name": "Old Laptop",
                    "vendor_name": "HP",
                    "friendly_name": "Old Laptop",
                    "status": "offline",
                    "first_seen": "2026-02-01T10:00:00Z",
                    "last_seen": "2026-03-03T20:00:00Z",
                },
            ],
            "total_merged": 2,
            "unmatched_deco_clients": [],
            "unmatched_deco_count": 0,
            "unmatched_lan_devices": 0,
            "timestamp": datetime.now().isoformat(),
            "correlation_stats": {
                "total_deco_clients": 2,
                "total_lan_devices": 2,
                "total_merged": 2,
                "correlation_percentage": 100.0,
            },
        }

        response = client.get("/api/deco/topology")
        data = response.json()
        devices = data["devices"]

        # Check that offline device is included
        offline_devices = [d for d in devices if d["status"] == "offline"]
        assert len(offline_devices) == 1
        assert offline_devices[0]["device_name"] == "Old Laptop"

    def test_topology_timestamp_present(self):
        """Test that timestamp is present in response"""
        response = client.get("/api/deco/topology")
        data = response.json()

        assert data["timestamp"] is not None
        # Verify timestamp is ISO format
        try:
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("Timestamp is not in ISO format")

    def test_topology_empty_nodes(self):
        """Test topology with no nodes"""
        self.mock_deco_service.get_nodes_with_details.return_value = []
        self.mock_deco_service.deco_client.get_client_list.return_value = []
        self.mock_correlation_service.get_merged_clients.return_value = {
            "merged_devices": [],
            "total_merged": 0,
            "unmatched_deco_clients": [],
            "unmatched_deco_count": 0,
            "unmatched_lan_devices": 0,
            "timestamp": datetime.now().isoformat(),
            "correlation_stats": {
                "total_deco_clients": 0,
                "total_lan_devices": 0,
                "total_merged": 0,
                "correlation_percentage": 0,
            },
        }

        response = client.get("/api/deco/topology")
        data = response.json()

        assert data["total_nodes"] == 0
        assert data["total_devices"] == 0
        assert data["total_relationships"] == 0

    def test_topology_api_error_handling(self):
        """Test topology endpoint error handling"""
        # Mock an API error
        self.mock_deco_service.get_nodes_with_details.side_effect = Exception("API Error")

        response = client.get("/api/deco/topology")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_topology_unauthorized_error(self):
        """Test topology endpoint with unauthorized error"""
        self.mock_deco_service.get_nodes_with_details.side_effect = Exception("401 Unauthorized")

        response = client.get("/api/deco/topology")

        assert response.status_code == 401
        data = response.json()
        assert "Not authenticated" in data.get("detail", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
