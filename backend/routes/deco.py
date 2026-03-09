"""
Deco API Routes
Endpoints for Deco node management and monitoring
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Create router for Deco endpoints
router = APIRouter(prefix="/api/deco", tags=["deco"])

# Global Deco service and correlation service instances (injected from main.py)
deco_service = None
correlation_service = None


# Request models
class WiFiConfigUpdate(BaseModel):
    """Request model for WiFi configuration update"""
    ssid: Optional[str] = None
    password: Optional[str] = None
    band_steering: Optional[bool] = None


class AlexaNameSyncRequest(BaseModel):
    """Request model for syncing names from Alexa links."""
    overwrite_existing: bool = False


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


@router.post("/auto-name-nodes")
async def auto_name_deco_nodes() -> Dict[str, Any]:
    """Auto-name network devices that match Deco node MACs."""
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        nodes = deco_service.get_nodes_with_details()
        named = 0
        for node in nodes:
            raw = node.get("raw_data", {})
            node_mac_raw = raw.get("deviceMac", "")
            node_name = node.get("node_name", "")
            if not node_mac_raw or not node_name:
                continue

            # Normalize MAC: "E4FAC45699FC" -> "e4:fa:c4:56:99:fc"
            mac_clean = node_mac_raw.lower().replace("-", "").replace(":", "")
            if len(mac_clean) == 12:
                normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
            else:
                continue

            # Try to find and name this network device
            if correlation_service and correlation_service.db:
                try:
                    with correlation_service.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE network_devices SET friendly_name = ? WHERE mac_address = ? AND (friendly_name IS NULL OR friendly_name = '')",
                            (f"Deco {node_name}", normalized),
                        )
                        conn.commit()
                        if cursor.rowcount > 0:
                            named += 1
                except Exception as e:
                    logger.warning(f"Failed to auto-name Deco node {node_name}: {e}")

        return {"success": True, "named": named, "total_nodes": len(nodes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-name nodes: {e}")


@router.get("/clients")
async def get_deco_clients() -> Dict[str, Any]:
    """Get raw Deco client list with names and MAC addresses.

    Tries cloud passthrough first, falls back to local API if cloud returns empty.
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        clients = deco_service.deco_client.get_client_list()

        # Fallback to local API if cloud returned empty
        if not clients:
            try:
                logger.info("Cloud client list empty, trying local Deco API fallback")
                clients = deco_service.deco_client.get_client_list_local()
            except Exception as local_err:
                logger.warning(f"Local API fallback also failed: {local_err}")

        return {
            "clients": clients,
            "total": len(clients),
        }
    except Exception as e:
        logger.error(f"Failed to fetch Deco clients: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch clients: {str(e)}")


@router.post("/import-client-names")
async def import_deco_client_names() -> Dict[str, Any]:
    """Import client names from local Deco API into network device records.

    Fetches the client list from the local Deco API (which has device names like
    "Alarm Backyard", "LeosRokuTV", etc.), matches by MAC address, and updates
    network_devices.friendly_name for unnamed devices.
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        clients = deco_service.deco_client.get_client_list_local()

        if not clients:
            return {"success": True, "imported": 0, "total_clients": 0, "clients": []}

        imported = 0
        if correlation_service and correlation_service.db:
            with correlation_service.db.get_connection() as conn:
                cursor = conn.cursor()
                for client in clients:
                    client_name = client.get("name", "")
                    client_mac = client.get("mac", "") or client.get("macAddress", "")
                    if not client_name or not client_mac:
                        continue

                    # Normalize MAC: "AA-BB-CC-DD-EE-FF" -> "aa:bb:cc:dd:ee:ff"
                    mac_clean = client_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
                    if len(mac_clean) == 12:
                        normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                    else:
                        continue

                    cursor.execute(
                        "UPDATE network_devices SET friendly_name = ? WHERE mac_address = ? AND (friendly_name IS NULL OR friendly_name = '')",
                        (client_name, normalized),
                    )
                    if cursor.rowcount > 0:
                        imported += 1

                conn.commit()

        return {
            "success": True,
            "imported": imported,
            "total_clients": len(clients),
            "clients": clients,
        }
    except Exception as e:
        logger.error(f"Failed to import Deco client names: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import client names: {str(e)}")


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


@router.post("/sync-names-from-alexa")
async def sync_deco_names_from_alexa(req: AlexaNameSyncRequest) -> Dict[str, Any]:
    """
    Sync linked Alexa device names into network device friendly names.

    This updates HomeSentinel's network device records so Deco views can display
    names aligned with Alexa naming.
    """
    if correlation_service is None:
        raise HTTPException(status_code=500, detail="Correlation service not initialized")

    try:
        result = correlation_service.sync_network_friendly_names_from_alexa(
            overwrite_existing=req.overwrite_existing
        )
        return result
    except Exception as e:
        logger.error(f"Failed to sync names from Alexa: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync names: {str(e)}")


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


@router.put("/wifi-config")
async def update_wifi_config(config_update: WiFiConfigUpdate) -> Dict[str, Any]:
    """
    Update WiFi configuration including SSID, password, and band steering

    Request body:
        - ssid: New SSID (1-32 characters, optional)
        - password: New password (8+ characters, optional)
        - band_steering: Enable/disable band steering (optional)

    Returns:
        JSON response containing:
        - success: Operation success status
        - message: Operation message
        - updated_config: Updated WiFi configuration
        - verification_status: Status of configuration verification ("pending", "verified", "timeout", "error")
        - timestamp: API response timestamp

    Raises:
        400: Invalid input parameters
        401: Not authenticated with Deco API
        429: Rate limit exceeded
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    # Validate input parameters
    if config_update.ssid is None and config_update.password is None and config_update.band_steering is None:
        raise HTTPException(
            status_code=400,
            detail="At least one parameter (ssid, password, or band_steering) must be provided"
        )

    try:
        # Call service to update WiFi config
        result = deco_service.update_wifi_config(
            ssid=config_update.ssid,
            password=config_update.password,
            band_steering=config_update.band_steering
        )

        return {
            "success": result.get("success", True),
            "message": result.get("message", "WiFi configuration updated successfully"),
            "updated_config": result.get("updated_config"),
            "verification_status": result.get("verification_status", "pending"),
            "timestamp": result.get("timestamp"),
        }

    except ValueError as e:
        # Validation errors
        logger.error(f"Validation error updating WiFi config: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update WiFi config: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        if "429" in str(e) or "rate limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
        raise HTTPException(status_code=500, detail=f"Failed to update WiFi config: {str(e)}")


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


@router.get("/topology")
async def get_topology() -> Dict[str, Any]:
    """
    Get network topology showing Deco nodes and their connected devices

    Returns:
        JSON response containing:
        - nodes: List of Deco nodes with their properties:
            - node_id: Unique node identifier
            - node_name: Human-readable node name
            - mac_address: Node MAC address (for device relationships)
            - status: Node operational status (online/offline)
            - signal_strength: Signal strength percentage (0-100)
            - connected_clients: Number of connected clients
        - devices: List of connected devices with their properties:
            - device_id: Unique device identifier
            - mac_address: Device MAC address
            - device_name: Device name (friendly or Deco client name)
            - status: Device status (online/offline)
            - friendly_name: User-defined device name
            - vendor_name: Device vendor/manufacturer
        - relationships: List of device-to-node connections:
            - device_id: Connected device ID
            - device_mac: Device MAC address
            - node_id: Associated Deco node ID
            - node_mac: Node MAC address (for visual connection line)
        - total_nodes: Total number of nodes
        - total_devices: Total number of devices
        - total_relationships: Total number of device-to-node relationships
        - timestamp: API response timestamp

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None or correlation_service is None:
        raise HTTPException(status_code=500, detail="Services not initialized")

    try:
        # Get all Deco nodes
        nodes_data = deco_service.get_nodes_with_details()

        # Get merged client data (devices with their Deco connections)
        merged_result = correlation_service.get_merged_clients()
        merged_devices = merged_result.get("merged_devices", [])

        # Get raw Deco clients to extract node associations
        deco_clients = deco_service.deco_client.get_client_list()

        # Build nodes list for topology (include MAC for relationships)
        nodes = []
        node_id_to_mac = {}
        for node in nodes_data:
            # Extract MAC from raw data if available, otherwise use node_id
            node_mac = node.get("raw_data", {}).get("macAddress") or node.get("raw_data", {}).get("mac_address") or node.get("node_id")
            node_id_to_mac[node.get("node_id")] = node_mac

            nodes.append({
                "node_id": node.get("node_id"),
                "node_name": node.get("node_name"),
                "mac_address": node_mac,
                "status": node.get("status"),
                "signal_strength": node.get("signal_strength"),
                "connected_clients": node.get("connected_clients"),
            })

        # Build devices list (from merged clients)
        devices = []
        device_mac_to_id = {}
        for merged_device in merged_devices:
            device_mac = merged_device.get("mac_address", "")
            device_id = merged_device.get("device_id", "")
            device_mac_to_id[device_mac] = device_id

            devices.append({
                "device_id": device_id,
                "mac_address": device_mac,
                "device_name": merged_device.get("deco_client_name") or merged_device.get("friendly_name") or "Unknown",
                "status": merged_device.get("status"),
                "friendly_name": merged_device.get("friendly_name"),
                "vendor_name": merged_device.get("vendor_name"),
            })

        # Build relationships (device -> node connections)
        relationships = []
        seen_relationships = set()

        for deco_client in deco_clients:
            client_mac = deco_client.get("macAddress") or deco_client.get("mac_address") or ""
            node_id = deco_client.get("nodeID") or deco_client.get("node_id")

            if client_mac and node_id:
                # Normalize MAC for comparison
                normalized_client_mac = client_mac.lower().replace("-", ":").replace(" ", "")

                # Find device_id for this client
                device_id = None
                for merged_device in merged_devices:
                    merged_mac = merged_device.get("mac_address", "").lower().replace("-", ":").replace(" ", "")
                    if normalized_client_mac == merged_mac:
                        device_id = merged_device.get("device_id")
                        break

                # Get node MAC
                node_mac = node_id_to_mac.get(node_id, node_id)

                # Create relationship (avoid duplicates)
                rel_key = f"{device_id}_{node_id}"
                if rel_key not in seen_relationships and device_id:
                    relationships.append({
                        "device_id": device_id,
                        "device_mac": normalized_client_mac,
                        "node_id": node_id,
                        "node_mac": node_mac,
                    })
                    seen_relationships.add(rel_key)

        return {
            "nodes": nodes,
            "devices": devices,
            "relationships": relationships,
            "total_nodes": len(nodes),
            "total_devices": len(devices),
            "total_relationships": len(relationships),
            "timestamp": merged_result.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Failed to fetch topology: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch topology: {str(e)}")
