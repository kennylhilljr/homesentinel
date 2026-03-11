"""
Deco API Routes
Endpoints for Deco node management and monitoring
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
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

                    # 2026-03-09: Write to deco_name column (always overwrite with latest Deco name).
                    # Also set friendly_name if it's currently empty.
                    cursor.execute(
                        "UPDATE network_devices SET deco_name = ? WHERE mac_address = ?",
                        (client_name, normalized),
                    )
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


@router.post("/rename-client")
async def rename_deco_client(request: Request) -> Dict[str, Any]:
    """Rename a client device on the Deco router and update network_devices.

    # 2026-03-09: Called from dashboard table when user selects a name from the
    # mismatch dropdown or enters a custom name and chooses "Write to Deco".

    Body: { "mac_address": "aa:bb:cc:dd:ee:ff", "new_name": "Kitchen Echo" }
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    body = await request.json()
    mac_address = body.get("mac_address", "")
    new_name = body.get("new_name", "")

    if not mac_address or not new_name:
        raise HTTPException(status_code=400, detail="mac_address and new_name are required")

    try:
        deco_service.deco_client.rename_client(mac_address, new_name)
    except Exception as e:
        logger.error(f"Deco rename failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rename on Deco: {str(e)}")

    # Update deco_name in network_devices
    if correlation_service and correlation_service.db:
        mac_clean = mac_address.lower().replace("-", "").replace(":", "").replace(" ", "")
        if len(mac_clean) == 12:
            normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
            with correlation_service.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE network_devices SET deco_name = ?, friendly_name = ? WHERE mac_address = ?",
                    (new_name, new_name, normalized),
                )
                conn.commit()

    return {"success": True, "mac_address": mac_address, "new_name": new_name}


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


# 2026-03-10: Lightweight endpoint returning client MAC → connected Deco node name.
# Used by the dashboard to show which Deco each device is connected to.
@router.get("/client-node-map")
async def get_client_node_map() -> Dict[str, Any]:
    """Return a mapping of client MAC addresses to their connected Deco node names."""
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        import base64
        client = deco_service.deco_client

        # 2026-03-11: Use get_topology_local() which creates its own local session.
        # This avoids 'NoneType aes_encrypt' errors from using the cloud client for local API.
        local_data = None
        try:
            local_data = client.get_topology_local()
        except Exception as e:
            logger.warning(f"Local topology fetch failed for client-node-map: {e}")

        node_names = {}
        mapping = {}

        if local_data and local_data.get("nodes"):
            for node in local_data["nodes"]:
                node_mac = node.get("mac", "")
                nickname = node.get("nickname", "")
                try:
                    nickname = base64.b64decode(nickname).decode("utf-8")
                except Exception:
                    pass
                node_names[node_mac] = nickname or node.get("device_model", node_mac)

            for node_mac, clients in local_data.get("node_clients", {}).items():
                node_name = node_names.get(node_mac, node_mac)
                for c in clients:
                    raw_mac = c.get("mac", "")
                    mac_clean = raw_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
                    if len(mac_clean) == 12:
                        normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                        mapping[normalized] = {
                            "node_name": node_name,
                            "node_mac": node_mac,
                            "connection_type": c.get("connection_type", ""),
                            "client_mesh": c.get("client_mesh", False),
                        }

        return {
            "client_node_map": mapping,
            "nodes": node_names,
            "total_mapped": len(mapping),
        }
    except Exception as e:
        logger.error(f"Failed to build client-node map: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to build client-node map: {str(e)}")


# 2026-03-10: Toggle mesh steering per client device.
@router.post("/client-mesh")
async def set_client_mesh(request: Request) -> Dict[str, Any]:
    """Toggle mesh steering for a specific client device."""
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        body = await request.json()
        mac_address = body.get("mac_address")
        mesh_enabled = body.get("mesh_enabled")

        if not mac_address or mesh_enabled is None:
            raise HTTPException(status_code=400, detail="mac_address and mesh_enabled are required")

        client = deco_service.deco_client
        result = client.set_client_mesh(mac_address, bool(mesh_enabled))
        error_code = result.get("error_code", -1)

        return {
            "success": error_code == 0,
            "mac_address": mac_address,
            "mesh_enabled": mesh_enabled,
            "error_code": error_code,
            "raw_response": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set client mesh: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set client mesh: {str(e)}")


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

        import base64

        # 2026-03-11: Use get_topology_local() which creates its own local session.
        client = deco_service.deco_client
        local_data = None
        try:
            local_data = client.get_topology_local()
        except Exception as e:
            logger.warning(f"Local topology fetch failed: {e}")

        local_nodes = local_data.get("nodes", []) if local_data else []
        local_node_clients = local_data.get("node_clients", {}) if local_data else {}

        # Build nodes list for topology
        nodes = []
        node_mac_to_name = {}
        client_to_node = {}
        deco_clients = {}

        if local_nodes:
            for node in local_nodes:
                node_mac = node.get("mac", "")
                nickname = node.get("nickname", "")
                try:
                    nickname = base64.b64decode(nickname).decode("utf-8")
                except Exception:
                    pass
                node_name = nickname or node.get("device_model", node_mac)
                node_mac_to_name[node_mac] = node_name
                role = node.get("role", "")

                # Enrich with cloud data if available
                enriched = {}
                for nd in nodes_data:
                    cloud_mac = nd.get("raw_data", {}).get("deviceMac", "")
                    if cloud_mac and cloud_mac.lower().replace("-", "") == node_mac.lower().replace("-", ""):
                        enriched = nd
                        break

                nodes.append({
                    "node_id": node_mac,
                    "node_name": node_name,
                    "mac_address": node_mac,
                    "status": enriched.get("status", "online" if role else "unknown"),
                    "signal_strength": enriched.get("signal_strength", 0),
                    "connected_clients": enriched.get("connected_clients", 0),
                    "role": role,
                })
        else:
            # Fallback: build nodes from cloud API data with deviceMac
            logger.warning("No local nodes, falling back to cloud nodes for topology")
            for nd in nodes_data:
                cloud_mac_raw = nd.get("raw_data", {}).get("deviceMac", "")
                if not cloud_mac_raw:
                    continue
                mac_clean = cloud_mac_raw.lower().replace("-", "").replace(":", "")
                if len(mac_clean) == 12:
                    node_mac = "-".join(mac_clean[i:i+2].upper() for i in range(0, 12, 2))
                else:
                    node_mac = cloud_mac_raw
                node_name = nd.get("node_name", nd.get("raw_data", {}).get("alias", node_mac))
                node_mac_to_name[node_mac] = node_name

                nodes.append({
                    "node_id": node_mac,
                    "node_name": node_name,
                    "mac_address": node_mac,
                    "status": nd.get("status", "online"),
                    "signal_strength": nd.get("signal_strength", 0),
                    "connected_clients": nd.get("connected_clients", 0),
                    "role": "",
                })

        # Build per-node client mapping from local API data
        for node_mac, clients in local_node_clients.items():
            node_name = node_mac_to_name.get(node_mac, node_mac)
            for c in clients:
                raw_mac = c.get("mac", "")
                mac_clean = raw_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
                if len(mac_clean) == 12:
                    normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                    client_to_node[normalized] = {
                        "node_mac": node_mac,
                        "node_name": node_name,
                        "connection_type": c.get("connection_type", ""),
                        "client_mesh": c.get("client_mesh", False),
                    }
                    deco_clients[normalized] = c

        # Update node connected_clients counts from actual per-node queries
        node_client_counts = {}
        for info in client_to_node.values():
            nm = info["node_mac"]
            node_client_counts[nm] = node_client_counts.get(nm, 0) + 1
        for node in nodes:
            node["connected_clients"] = node_client_counts.get(node["mac_address"], 0)

        # Build devices list — prefer merged DB data, fall back to raw Deco clients
        devices = []
        if merged_devices:
            for merged_device in merged_devices:
                device_mac = merged_device.get("mac_address", "")
                device_id = merged_device.get("device_id", "")
                devices.append({
                    "device_id": device_id,
                    "mac_address": device_mac,
                    "device_name": merged_device.get("deco_client_name") or merged_device.get("friendly_name") or "Unknown",
                    "status": merged_device.get("status"),
                    "friendly_name": merged_device.get("friendly_name"),
                    "vendor_name": merged_device.get("vendor_name"),
                    "current_ip": merged_device.get("current_ip", ""),
                    "connection_type": client_to_node.get(device_mac.lower(), {}).get("connection_type", ""),
                })
        else:
            # Fallback: build devices directly from Deco local API client data
            logger.info(f"No merged devices, building from {len(deco_clients)} Deco clients")
            for mac, dc in deco_clients.items():
                dc_name = dc.get("name", "")
                try:
                    dc_name = base64.b64decode(dc_name).decode("utf-8")
                except Exception:
                    pass
                devices.append({
                    "device_id": mac,
                    "mac_address": mac,
                    "device_name": dc_name or "Unknown",
                    "status": "online" if dc.get("online") else "offline",
                    "friendly_name": dc_name,
                    "vendor_name": "",
                    "current_ip": dc.get("ip", ""),
                    "connection_type": client_to_node.get(mac, {}).get("connection_type", ""),
                })

        # Build relationships from per-node client mapping
        relationships = []
        seen = set()
        all_device_macs = {d["mac_address"].lower() for d in devices}
        # Also add any Deco clients not in the device list
        for mac in client_to_node:
            if mac not in all_device_macs:
                dc = deco_clients.get(mac, {})
                dc_name = dc.get("name", "")
                try:
                    dc_name = base64.b64decode(dc_name).decode("utf-8")
                except Exception:
                    pass
                devices.append({
                    "device_id": mac,
                    "mac_address": mac,
                    "device_name": dc_name or "Unknown",
                    "status": "online" if dc.get("online") else "offline",
                    "friendly_name": dc_name,
                    "vendor_name": "",
                    "current_ip": dc.get("ip", ""),
                    "connection_type": client_to_node[mac].get("connection_type", ""),
                })
                all_device_macs.add(mac)

        for device in devices:
            device_mac = device["mac_address"].lower()
            device_id = device["device_id"]
            node_info = client_to_node.get(device_mac)
            if node_info and device_id:
                rel_key = f"{device_id}_{node_info['node_mac']}"
                if rel_key not in seen:
                    relationships.append({
                        "device_id": device_id,
                        "device_mac": device_mac,
                        "node_id": node_info["node_mac"],
                        "node_mac": node_info["node_mac"],
                        "connection_type": node_info["connection_type"],
                    })
                    seen.add(rel_key)

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


# 2026-03-11: NetworkX-based topology graph rendered as SVG.
@router.get("/topology-graph")
async def get_topology_graph() -> Response:
    """Generate an SVG network topology graph using NetworkX."""
    import io
    import base64
    import json as _json

    try:
        import networkx as nx
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Missing dependency: {e}")

    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        client = deco_service.deco_client

        # 2026-03-11: Use get_topology_local() for a clean local session
        local_data = None
        try:
            local_data = client.get_topology_local()
        except Exception as e:
            logger.warning(f"Local topology fetch failed for graph: {e}")

        local_nodes = local_data.get("nodes", []) if local_data else []
        node_clients = local_data.get("node_clients", {}) if local_data else {}

        node_mac_to_name = {}
        if local_nodes:
            for node in local_nodes:
                node_mac = node.get("mac", "")
                nickname = node.get("nickname", "")
                try:
                    nickname = base64.b64decode(nickname).decode("utf-8")
                except Exception:
                    pass
                node_mac_to_name[node_mac] = nickname or node.get("device_model", node_mac)
        else:
            cloud_nodes = deco_service.get_nodes_with_details()
            for nd in cloud_nodes:
                cloud_mac_raw = nd.get("raw_data", {}).get("deviceMac", "")
                if not cloud_mac_raw:
                    continue
                mac_clean = cloud_mac_raw.lower().replace("-", "").replace(":", "")
                if len(mac_clean) == 12:
                    node_mac = "-".join(mac_clean[i:i+2].upper() for i in range(0, 12, 2))
                else:
                    node_mac = cloud_mac_raw
                node_mac_to_name[node_mac] = nd.get("node_name", nd.get("raw_data", {}).get("alias", node_mac))

        # Build NetworkX graph
        G = nx.Graph()

        # Add router (internet) node at center
        G.add_node("internet", label="Internet", node_type="internet")

        # Add Deco nodes and connect to internet
        for node_mac, node_name in node_mac_to_name.items():
            G.add_node(node_mac, label=node_name, node_type="deco")
            G.add_edge("internet", node_mac)

        # Add client devices
        conn_colors = {
            "band5": "#1565C0",
            "band2_4": "#2E7D32",
            "band6": "#283593",
            "wired": "#C62828",
        }
        for node_mac, clients in node_clients.items():
            for c in clients:
                raw_mac = c.get("mac", "")
                mac_clean = raw_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
                if len(mac_clean) != 12:
                    continue
                normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))

                dc_name = c.get("name", "")
                try:
                    dc_name = base64.b64decode(dc_name).decode("utf-8")
                except Exception:
                    pass

                conn_type = c.get("connection_type", "")
                is_online = c.get("online", False)
                ip_addr = c.get("ip", "")

                # Build label: name + IP + MAC
                label_parts = [dc_name or "Unknown"]
                if ip_addr:
                    label_parts.append(ip_addr)
                label_parts.append(normalized)

                G.add_node(normalized,
                           label="\n".join(label_parts),
                           node_type="device",
                           online=is_online,
                           connection_type=conn_type)
                G.add_edge(node_mac, normalized, connection_type=conn_type)

        # Layout: use spring layout with Deco nodes as fixed positions in a circle
        # Place internet at center, Deco nodes in inner ring, devices in outer ring
        import math
        pos = {}
        deco_macs = list(node_mac_to_name.keys())
        n_decos = len(deco_macs)

        pos["internet"] = (0, 0)
        for i, dm in enumerate(deco_macs):
            angle = 2 * math.pi * i / max(n_decos, 1)
            pos[dm] = (2.5 * math.cos(angle), 2.5 * math.sin(angle))

        # Use spring layout for devices, seeded with fixed deco/internet positions
        if len(G.nodes) > len(deco_macs) + 1:
            fixed_nodes = ["internet"] + deco_macs
            seed_pos = {n: pos.get(n, (0, 0)) for n in G.nodes}
            # Give devices initial positions near their deco node
            for node_mac, clients in node_clients.items():
                deco_pos = pos.get(node_mac, (0, 0))
                for idx, c in enumerate(clients):
                    raw_mac = c.get("mac", "")
                    mac_clean = raw_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
                    if len(mac_clean) == 12:
                        normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                        angle_offset = 2 * math.pi * idx / max(len(clients), 1)
                        seed_pos[normalized] = (
                            deco_pos[0] + 1.8 * math.cos(angle_offset),
                            deco_pos[1] + 1.8 * math.sin(angle_offset),
                        )
            pos = nx.spring_layout(G, pos=seed_pos, fixed=fixed_nodes, k=1.5, iterations=50, seed=42)

        # Draw the graph
        fig, ax = plt.subplots(1, 1, figsize=(18, 14))
        fig.patch.set_facecolor('#f3f6fa')
        ax.set_facecolor('#f3f6fa')

        # Categorize nodes
        internet_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "internet"]
        deco_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "deco"]
        online_devices = [n for n, d in G.nodes(data=True) if d.get("node_type") == "device" and d.get("online")]
        offline_devices = [n for n, d in G.nodes(data=True) if d.get("node_type") == "device" and not d.get("online")]

        # Draw edges with connection type colors
        for u, v, data in G.edges(data=True):
            ct = data.get("connection_type", "")
            color = conn_colors.get(ct, "#B0BEC5")
            linewidth = 2.0 if ct == "wired" else 1.2
            linestyle = "-" if ct else "--"
            nx.draw_networkx_edges(G, pos, edgelist=[(u, v)],
                                   edge_color=color, width=linewidth,
                                   style=linestyle, alpha=0.6, ax=ax)

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, nodelist=internet_nodes,
                               node_color="#FF6F00", node_size=800,
                               node_shape="s", edgecolors="#E65100",
                               linewidths=2, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=deco_nodes,
                               node_color="#1E8B52", node_size=600,
                               node_shape="h", edgecolors="#145E37",
                               linewidths=2, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=online_devices,
                               node_color="#42A5F5", node_size=200,
                               node_shape="o", edgecolors="#1565C0",
                               linewidths=1, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=offline_devices,
                               node_color="#BDBDBD", node_size=150,
                               node_shape="o", edgecolors="#757575",
                               linewidths=1, alpha=0.5, ax=ax)

        # Draw labels
        deco_labels = {n: G.nodes[n].get("label", n) for n in deco_nodes}
        internet_labels = {"internet": "Internet"}
        device_labels = {}
        for n in online_devices + offline_devices:
            device_labels[n] = G.nodes[n].get("label", n)

        nx.draw_networkx_labels(G, pos, labels=internet_labels,
                                font_size=10, font_weight="bold",
                                font_color="white", ax=ax)
        # Deco labels offset above
        deco_label_pos = {n: (pos[n][0], pos[n][1] + 0.35) for n in deco_nodes}
        nx.draw_networkx_labels(G, deco_label_pos, labels=deco_labels,
                                font_size=9, font_weight="bold",
                                font_color="#0f1a2a", ax=ax)
        # Device labels offset below
        device_label_pos = {n: (pos[n][0], pos[n][1] - 0.25) for n in device_labels}
        nx.draw_networkx_labels(G, device_label_pos, labels=device_labels,
                                font_size=5.5, font_color="#37474F", ax=ax)

        # Legend
        legend_items = [
            mpatches.Patch(color="#FF6F00", label="Internet Gateway"),
            mpatches.Patch(color="#1E8B52", label="Deco Node"),
            mpatches.Patch(color="#42A5F5", label="Device (Online)"),
            mpatches.Patch(color="#BDBDBD", label="Device (Offline)"),
            mpatches.Patch(color="#1565C0", label="5 GHz"),
            mpatches.Patch(color="#2E7D32", label="2.4 GHz"),
            mpatches.Patch(color="#283593", label="6 GHz"),
            mpatches.Patch(color="#C62828", label="Wired"),
        ]
        ax.legend(handles=legend_items, loc="upper left", fontsize=8,
                  framealpha=0.9, fancybox=True)

        ax.set_title(f"Network Topology — {len(deco_nodes)} Nodes, "
                     f"{len(online_devices) + len(offline_devices)} Devices",
                     fontsize=14, fontweight="bold", color="#0f1a2a", pad=15)
        ax.axis("off")
        plt.tight_layout()

        # Render to SVG
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)
        svg_data = buf.getvalue()

        return Response(content=svg_data, media_type="image/svg+xml")

    except Exception as e:
        logger.error(f"Failed to generate topology graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate topology graph: {str(e)}")
