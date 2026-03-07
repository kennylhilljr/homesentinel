"""
Deco API Routes
Endpoints for Deco node management and monitoring
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Create router for Deco endpoints
router = APIRouter(prefix="/api/deco", tags=["deco"])

# Global Deco service and correlation service instances (injected from main.py)
deco_service = None
correlation_service = None


def set_deco_service(service):
    """
    Set the Deco service instance

    Args:
        service: DecoService instance
    """
    global deco_service
    deco_service = service


def set_correlation_service(service):
    """
    Set the correlation service instance

    Args:
        service: CorrelationService instance
    """
    global correlation_service
    correlation_service = service


@router.get("/nodes")
async def get_deco_nodes() -> Dict[str, Any]:
    """
    Get list of Deco nodes with detailed status information

    Returns:
        JSON response containing:
        - nodes: List of node dictionaries with details
        - total: Total number of nodes
        - timestamp: API response timestamp
        - cache_info: Cache status and age

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        nodes = deco_service.get_nodes_with_details()

        return {
            "nodes": nodes,
            "total": len(nodes),
            "timestamp": nodes[0]["last_updated"] if nodes else None,
            "cache_info": {
                "ttl_seconds": deco_service.CACHE_TTL,
                "cached": deco_service._nodes_cache is not None,
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch Deco nodes: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch nodes: {str(e)}")


@router.get("/nodes/{node_id}")
async def get_deco_node(node_id: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific Deco node

    Args:
        node_id: Unique node identifier

    Returns:
        JSON response containing:
        - node: Node details dictionary
        - timestamp: API response timestamp

    Raises:
        404: Node not found
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        node = deco_service.get_node_by_id(node_id)

        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        return {
            "node": node,
            "timestamp": node["last_updated"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch node {node_id}: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch node: {str(e)}")


@router.post("/nodes/refresh")
async def refresh_deco_nodes() -> Dict[str, Any]:
    """
    Manually refresh Deco node list (bypass cache)

    Returns:
        JSON response containing:
        - success: Operation success status
        - nodes: List of refreshed node dictionaries
        - message: Operation message
        - timestamp: API response timestamp

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        # Clear cache to force refresh
        deco_service.clear_cache()
        nodes = deco_service.get_nodes_with_details()

        return {
            "success": True,
            "nodes": nodes,
            "message": f"Refreshed {len(nodes)} nodes",
            "timestamp": nodes[0]["last_updated"] if nodes else None,
        }

    except Exception as e:
        logger.error(f"Failed to refresh Deco nodes: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to refresh nodes: {str(e)}")


@router.get("/clients-merged")
async def get_merged_deco_clients() -> Dict[str, Any]:
    """
    Get merged view of Deco connected clients and locally-discovered devices

    Correlates Deco mesh network clients with NetworkDevices by MAC address,
    providing a unified view with both Deco client names and local network data
    (IP addresses, vendor info, friendly names, etc).

    Returns:
        JSON response containing:
        - merged_devices: List of correlated devices with both Deco and LAN data
        - total_merged: Count of successfully correlated devices
        - unmatched_deco_clients: List of Deco clients without local network match
        - unmatched_deco_count: Count of unmatched Deco clients
        - unmatched_lan_devices: Count of local devices without Deco client match
        - timestamp: API response timestamp
        - correlation_stats: Statistics about the correlation

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized

    Example response:
        {
            "merged_devices": [
                {
                    "device_id": "uuid",
                    "mac_address": "00:11:22:33:44:55",
                    "current_ip": "192.168.1.50",
                    "deco_client_name": "iPhone",
                    "vendor_name": "APPLE",
                    "friendly_name": "john-iphone",
                    "status": "online",
                    "first_seen": "2026-03-01T10:00:00Z",
                    "last_seen": "2026-03-07T02:23:00Z"
                }
            ],
            "total_merged": 5,
            "unmatched_deco_clients": [],
            "unmatched_deco_count": 0,
            "unmatched_lan_devices": 2,
            "timestamp": "2026-03-07T02:25:00Z",
            "correlation_stats": {
                "total_deco_clients": 5,
                "total_lan_devices": 7,
                "total_merged": 5,
                "correlation_percentage": 100.0
            }
        }
    """
    if correlation_service is None:
        raise HTTPException(status_code=500, detail="Correlation service not initialized")

    try:
        result = correlation_service.get_merged_clients()
        return result

    except Exception as e:
        logger.error(f"Failed to get merged Deco clients: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to get merged clients: {str(e)}")


@router.get("/wifi-config")
async def get_wifi_config() -> Dict[str, Any]:
    """
    Get WiFi configuration including SSID, bands, and channel settings

    Returns:
        JSON response containing:
        - ssid: Network SSID/name
        - bands: List of supported bands (2.4 GHz, 5 GHz, 6 GHz)
        - channel_2_4ghz: Current 2.4 GHz channel
        - channel_5ghz: Current 5 GHz channel
        - channel_6ghz: Current 6 GHz channel (if available)
        - band_steering_enabled: Whether band steering is enabled
        - timestamp: API response timestamp
        - cache_info: Cache status and age

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        wifi_config = deco_service.get_wifi_config()

        return {
            "ssid": wifi_config.get("ssid"),
            "bands": wifi_config.get("bands"),
            "channel_2_4ghz": wifi_config.get("channel_2_4ghz"),
            "channel_5ghz": wifi_config.get("channel_5ghz"),
            "channel_6ghz": wifi_config.get("channel_6ghz"),
            "band_steering_enabled": wifi_config.get("band_steering_enabled"),
            "timestamp": wifi_config.get("last_updated"),
            "cache_info": {
                "ttl_seconds": deco_service.CACHE_TTL,
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch WiFi config: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WiFi config: {str(e)}")


@router.get("/qos")
async def get_qos_settings() -> Dict[str, Any]:
    """
    Get QoS (Quality of Service) settings and per-device bandwidth allocation

    Returns:
        JSON response containing:
        - qos_enabled: Whether QoS is enabled
        - devices: List of devices with QoS settings:
            - device_name: Device name
            - mac_address: MAC address
            - priority: Priority level (High/Normal/Low)
            - bandwidth_limit_mbps: Bandwidth limit in Mbps
            - connection_type: WiFi/Wired
            - ip_address: IP address
        - total_devices: Total number of devices
        - timestamp: API response timestamp
        - cache_info: Cache status and age

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        qos_data = deco_service.get_qos_settings()

        return {
            "qos_enabled": qos_data.get("qos_enabled"),
            "devices": qos_data.get("devices"),
            "total_devices": qos_data.get("total_devices"),
            "timestamp": qos_data.get("last_updated"),
            "cache_info": {
                "ttl_seconds": deco_service.CACHE_TTL,
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch QoS settings: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch QoS settings: {str(e)}")
