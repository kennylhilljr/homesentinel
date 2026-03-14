"""
Deco API Routes
Endpoints for Deco node management and monitoring
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)

# Create router for Deco endpoints
router = APIRouter(prefix="/api/deco", tags=["deco"])

# Global Deco service and correlation service instances (injected from main.py)
deco_service = None
correlation_service = None

# 2026-03-13: Route-level cache for topology responses (avoids re-querying Deco + matplotlib on every page load)
_topology_json_cache = None
_topology_json_cache_time = 0
_topology_svg_cache = None
_topology_svg_cache_time = 0
TOPOLOGY_ROUTE_CACHE_TTL = 60  # seconds — Deco data doesn't change frequently


def _remap_role(role: str) -> str:
    """2026-03-13: Remap Deco API 'master'/'slave' to 'primary'/'secondary' for display."""
    if role == "master":
        return "primary"
    if role == "slave":
        return "secondary"
    return role


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


def _get_node_friendly_name(node_mac: str) -> Optional[str]:
    """Look up the friendly_name from network_devices for a Deco node MAC.

    2026-03-11: The Deco local API nickname field can get corrupted with client
    device names (e.g. 'Kenny's Echo show' instead of 'Office'). We prefer
    the HomeSentinel-stored friendly_name which the user sets manually.
    """
    if not deco_service or not deco_service._device_repo:
        return None
    try:
        mac_clean = node_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
        if len(mac_clean) != 12:
            return None
        normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
        with deco_service._device_repo.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT friendly_name FROM network_devices WHERE LOWER(mac_address) = ?",
                (normalized,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return None


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
        # 2026-03-11: Rich node info with backhaul type for signal icons
        node_details = {}
        mapping = {}

        if local_data and local_data.get("nodes"):
            for node in local_data["nodes"]:
                node_mac = node.get("mac", "")
                nickname = node.get("nickname", "")
                try:
                    nickname = base64.b64decode(nickname).decode("utf-8")
                except Exception:
                    pass
                # 2026-03-11: Prefer HomeSentinel friendly_name over Deco nickname
                # (Deco nickname can get corrupted with client device names)
                db_name = _get_node_friendly_name(node_mac)
                display_name = db_name or nickname or node.get("device_model", node_mac)
                node_names[node_mac] = display_name
                # connection_type for nodes = backhaul type (list or string)
                ct = node.get("connection_type", [])
                if isinstance(ct, str):
                    ct = [ct]
                raw_role = node.get("role", "slave")
                role = _remap_role(raw_role)
                # Determine if wired backhaul
                node_name_lower = display_name.lower()
                is_wired_backhaul = (
                    raw_role == "master"
                    or "wired" in ct
                    or (ct and all(c not in ("band2_4", "band5", "band6") for c in ct))
                    or "dining" in node_name_lower
                )
                node_details[node_mac] = {
                    "name": display_name,
                    "role": role,
                    "backhaul": "wired" if is_wired_backhaul else "wireless",
                    "backhaul_bands": ct,
                }

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
                            # 2026-03-11: Pass wire_type and speed for signal indicator
                            "wire_type": c.get("wire_type", ""),
                            "down_speed": c.get("down_speed", 0),
                            "up_speed": c.get("up_speed", 0),
                        }

        return {
            "client_node_map": mapping,
            "nodes": node_names,
            "node_details": node_details,
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


# 2026-03-11: Trigger Deco mesh network optimization
@router.post("/optimize-network")
async def optimize_network() -> Dict[str, Any]:
    """Trigger Deco mesh network optimization.
    Re-evaluates channel assignments, band steering, and client-node associations.
    """
    if deco_service is None or deco_service.deco_client is None:
        raise HTTPException(status_code=503, detail="Deco service not available")
    try:
        result = deco_service.deco_client.optimize_network()
        error_code = result.get("error_code", -1)
        perf = result.get("performance", {})
        client_count = result.get("client_count", 0)
        cpu = perf.get("cpu_usage", "?")
        mem = perf.get("mem_usage", "?")
        return {
            "success": error_code == 0,
            "error_code": error_code,
            "message": f"Network refreshed — {client_count} clients, CPU: {cpu}%, Mem: {mem}%",
            "performance": perf,
            "client_count": client_count,
        }
    except Exception as e:
        logger.error(f"Failed to optimize network: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to optimize network: {str(e)}")


@router.get("/topology")
async def get_topology() -> Dict[str, Any]:
    """
    Get network topology showing Deco nodes and their connected devices.
    2026-03-13: Cached for 60s at route level to avoid slow Deco API re-queries.

    Returns:
        JSON with nodes, devices, relationships, totals, timestamp.
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

    # 2026-03-13: Return cached response if fresh
    global _topology_json_cache, _topology_json_cache_time
    now = time.time()
    if _topology_json_cache and (now - _topology_json_cache_time) < TOPOLOGY_ROUTE_CACHE_TTL:
        logger.debug("Returning cached topology JSON")
        return _topology_json_cache

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
                # 2026-03-11: Prefer HomeSentinel friendly_name over Deco nickname
                # (Deco nickname can get corrupted with client device names)
                db_name = _get_node_friendly_name(node_mac)
                node_name = db_name or nickname or node.get("device_model", node_mac)
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
                    # 2026-03-13: Include preferred_deco_node for pinned badge in topology cards
                    "preferred_deco_node": merged_device.get("preferred_deco_node"),
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

        # 2026-03-13: Remap master/slave → primary/secondary for display
        for node in nodes:
            if "role" in node:
                node["role"] = _remap_role(node["role"])

        result = {
            "nodes": nodes,
            "devices": devices,
            "relationships": relationships,
            "total_nodes": len(nodes),
            "total_devices": len(devices),
            "total_relationships": len(relationships),
            "timestamp": merged_result.get("timestamp"),
        }

        # 2026-03-13: Cache the result
        _topology_json_cache = result
        _topology_json_cache_time = time.time()

        return result

    except Exception as e:
        import traceback
        logger.error(f"Failed to fetch topology: {e}\n{traceback.format_exc()}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch topology: {str(e)}")


# 2026-03-11: NetworkX-based topology graph rendered as SVG.
@router.get("/topology-graph")
async def get_topology_graph() -> Response:
    """Generate an SVG network topology graph using NetworkX.
    2026-03-13: Cached for 60s to avoid re-rendering matplotlib SVG on every page load.
    """
    # 2026-03-13: Return cached SVG if fresh
    global _topology_svg_cache, _topology_svg_cache_time
    now = time.time()
    if _topology_svg_cache and (now - _topology_svg_cache_time) < TOPOLOGY_ROUTE_CACHE_TTL:
        logger.debug("Returning cached topology SVG")
        return Response(content=_topology_svg_cache, media_type="image/svg+xml")

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
                # 2026-03-11: Prefer HomeSentinel friendly_name over Deco nickname
                db_name = _get_node_friendly_name(node_mac)
                node_mac_to_name[node_mac] = db_name or nickname or node.get("device_model", node_mac)
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

        # 2026-03-11: Fetch Chester 5G signal data for tower/band info
        chester_info = {}
        try:
            from routes.chester import chester_service as _chester_svc
            if _chester_svc:
                chester_info = _chester_svc.get_system_info()
        except Exception as e:
            logger.warning(f"Chester info fetch failed for topology: {e}")

        # Build NetworkX graph
        G = nx.Graph()

        # 2026-03-11: Physical topology chain:
        # T-Mobile Tower → Waveform MIMO → Chester 5G → Deco Office → other Decos → devices
        #
        # Build tower label with cell info from Chester
        tower_label = "T-Mobile\nCell Tower"
        cell_id = chester_info.get("cell_id", "")
        if cell_id:
            tower_label += f"\nCellID: {cell_id}"

        # 2026-03-11: Build clean band labels for the tower-to-waveform link
        import re as _re
        ca_bands = chester_info.get("ca_band", [])
        conn_type_str = chester_info.get("connection_type", "NR5G-SA")
        band_str = chester_info.get("band", "")
        tower_bands = []
        for cab in ca_bands:
            # Extract just the band name (e.g. "NR5G BAND 41") from raw AT output
            band_matches = _re.findall(r'((?:NR5G|LTE)\s+BAND\s+\d+)', str(cab), _re.IGNORECASE)
            if band_matches:
                for bm in band_matches:
                    clean = bm.strip()
                    if clean not in tower_bands:
                        tower_bands.append(clean)
            else:
                # Fallback: use as-is but truncate
                clean = str(cab).strip().strip('"')[:30]
                if clean:
                    tower_bands.append(clean)
        if not tower_bands and band_str:
            tower_bands.append(f"Band {band_str}")

        # Build Chester label
        chester_label = "5G Chester AX3000 - SDX75"
        chester_ip = chester_info.get("ipv4_addr", "")
        if chester_ip:
            chester_label += f"\n{chester_ip}"

        # Signal info for Chester
        rsrp = chester_info.get("rsrp", "")
        sinr = chester_info.get("sinr", "")
        signal_label = ""
        if rsrp:
            signal_label += f"RSRP: {rsrp} dBm"
        if sinr:
            signal_label += f"  SINR: {sinr} dBm"

        G.add_node("tower", label=tower_label, node_type="tower")
        G.add_node("waveform", label="Waveform\nQualcomm MIMO", node_type="waveform")
        G.add_node("chester", label=chester_label, node_type="chester")

        # Tower ↔ Waveform (wireless 5G bands)
        band_edge_label = conn_type_str
        if tower_bands:
            band_edge_label = "\n".join(tower_bands)
        G.add_edge("tower", "waveform", connection_type="5g_tower",
                   label=band_edge_label)
        # Waveform ↔ Chester (coax/cable)
        G.add_edge("waveform", "chester", connection_type="wired",
                   label="Coax" if not signal_label else signal_label)
        # Chester ↔ Deco Office (wired ethernet)
        # Add Deco nodes
        deco_macs = list(node_mac_to_name.keys())

        # Find the master Deco node (wired to Chester)
        master_mac = None
        for node in local_nodes:
            if node.get("role") == "master":
                master_mac = node.get("mac", "")
                break
        if not master_mac and deco_macs:
            master_mac = deco_macs[0]
        for node_mac, node_name in node_mac_to_name.items():
            G.add_node(node_mac, label=node_name, node_type="deco")

        # Chester → master Deco (wired)
        if master_mac:
            G.add_edge("chester", master_mac, connection_type="wired",
                       label="Ethernet")

        # 2026-03-11: Connect non-master Decos — check if wired or mesh backhaul
        # Build lookup of node connection info from local API data
        node_conn_types = {}
        for node in local_nodes:
            nmac = node.get("mac", "")
            # connection_type can be a list like ["band2_4","band5"] or include "wired"
            ct = node.get("connection_type", [])
            if isinstance(ct, str):
                ct = [ct]
            node_conn_types[nmac] = ct

        for node_mac in deco_macs:
            if node_mac != master_mac:
                ct_list = node_conn_types.get(node_mac, [])
                node_name_lower = node_mac_to_name.get(node_mac, "").lower()
                # Check if wired: API says "wired", or no wifi bands listed,
                # or known hardwired node (Dining Room is hardwired to Office)
                is_wired = (
                    "wired" in ct_list
                    or (ct_list and all(c not in ("band2_4", "band5", "band6") for c in ct_list))
                    or "dining" in node_name_lower
                )
                if is_wired:
                    G.add_edge(master_mac, node_mac, connection_type="wired",
                               label="Ethernet")
                else:
                    G.add_edge(master_mac, node_mac, connection_type="mesh_backhaul",
                               label="Mesh")

        # Add client devices
        conn_colors = {
            "band5": "#1565C0",
            "band2_4": "#2E7D32",
            "band6": "#283593",
            "wired": "#C62828",
            "5g_tower": "#9C27B0",
            "mesh_backhaul": "#FF9800",
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
                # 2026-03-11: Prefer DB friendly_name for device labels too
                db_dev_name = _get_node_friendly_name(raw_mac)

                conn_type = c.get("connection_type", "")
                is_online = c.get("online", False)
                ip_addr = c.get("ip", "")

                # 2026-03-11: Fall back to DB current_ip if Deco doesn't provide IP
                if not ip_addr:
                    try:
                        with deco_service._device_repo.db.get_connection() as db_conn:
                            row = db_conn.execute(
                                "SELECT current_ip FROM network_devices WHERE LOWER(mac_address) = ?",
                                (normalized,)
                            ).fetchone()
                            if row and row[0]:
                                ip_addr = row[0]
                    except Exception:
                        pass

                # Build label: name + IP + MAC
                display_name = db_dev_name or dc_name or "Unknown"
                label_parts = [display_name]
                if ip_addr:
                    label_parts.append(ip_addr)
                label_parts.append(normalized)

                G.add_node(normalized,
                           label="\n".join(label_parts),
                           node_type="device",
                           online=is_online,
                           connection_type=conn_type)
                G.add_edge(node_mac, normalized, connection_type=conn_type)

        # 2026-03-11: Horizontal layout — tower on left, devices on right
        import math
        pos = {}
        n_decos = len(deco_macs)

        # Horizontal chain: tower → waveform → chester → decos → devices
        pos["tower"] = (0, 0)
        pos["waveform"] = (3.5, 0)
        pos["chester"] = (7.0, 0)

        # Deco nodes fanned out vertically to the right of Chester
        deco_x = 11.0
        if n_decos == 1:
            pos[deco_macs[0]] = (deco_x, 0)
        else:
            for i, dm in enumerate(deco_macs):
                y_offset = (i - (n_decos - 1) / 2) * 2.5
                pos[dm] = (deco_x, y_offset)

        # Use spring layout for devices, seeded with fixed infrastructure positions
        infra_nodes = ["tower", "waveform", "chester"] + deco_macs
        if len(G.nodes) > len(infra_nodes):
            seed_pos = {n: pos.get(n, (0, 0)) for n in G.nodes}
            # Give devices initial positions to the right of their deco node
            for node_mac, clients in node_clients.items():
                deco_pos = pos.get(node_mac, (deco_x, 0))
                for idx, c in enumerate(clients):
                    raw_mac = c.get("mac", "")
                    mac_clean = raw_mac.lower().replace("-", "").replace(":", "").replace(" ", "")
                    if len(mac_clean) == 12:
                        normalized = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                        angle_offset = -math.pi / 3 + (2 * math.pi / 3) * idx / max(len(clients) - 1, 1)
                        seed_pos[normalized] = (
                            deco_pos[0] + 3.0,
                            deco_pos[1] + 2.0 * math.sin(angle_offset),
                        )
            pos = nx.spring_layout(G, pos=seed_pos, fixed=infra_nodes, k=1.5, iterations=50, seed=42)

        # Draw the graph — wide for horizontal layout
        fig, ax = plt.subplots(1, 1, figsize=(28, 14))
        fig.patch.set_facecolor('#f3f6fa')
        ax.set_facecolor('#f3f6fa')

        # Categorize nodes
        tower_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "tower"]
        waveform_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "waveform"]
        chester_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "chester"]
        deco_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "deco"]
        online_devices = [n for n, d in G.nodes(data=True) if d.get("node_type") == "device" and d.get("online")]
        offline_devices = [n for n, d in G.nodes(data=True) if d.get("node_type") == "device" and not d.get("online")]

        # Draw edges with connection type colors
        infra_edge_labels = []  # collect for manual placement
        for u, v, edata in G.edges(data=True):
            ct = edata.get("connection_type", "")
            color = conn_colors.get(ct, "#B0BEC5")
            linewidth = 1.2
            linestyle = "-" if ct else "--"
            nx.draw_networkx_edges(G, pos, edgelist=[(u, v)],
                                   edge_color=color, width=linewidth,
                                   style=linestyle, alpha=0.7, ax=ax)
            elabel = edata.get("label", "")
            if elabel:
                infra_edge_labels.append((u, v, elabel))

        # 2026-03-11: Draw edge labels manually with ax.text for guaranteed horizontal text
        for u, v, label_text in infra_edge_labels:
            ux, uy = pos[u]
            vx, vy = pos[v]
            mx, my = (ux + vx) / 2, (uy + vy) / 2
            ax.text(mx, my + 0.35, label_text,
                    fontsize=7, color="#4A148C", fontweight="bold",
                    ha="center", va="bottom", rotation=0,
                    bbox=dict(boxstyle="round,pad=0.3",
                              facecolor="white", alpha=0.9,
                              edgecolor="#CE93D8"))

        # Draw nodes — infrastructure chain
        nx.draw_networkx_nodes(G, pos, nodelist=tower_nodes,
                               node_color="#9C27B0", node_size=1000,
                               node_shape="^", edgecolors="#6A1B9A",
                               linewidths=2, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=waveform_nodes,
                               node_color="#E91E63", node_size=700,
                               node_shape="d", edgecolors="#AD1457",
                               linewidths=2, ax=ax)
        nx.draw_networkx_nodes(G, pos, nodelist=chester_nodes,
                               node_color="#FF6F00", node_size=900,
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

        # 2026-03-11: Draw infrastructure labels with ax.text for precise control
        for node_id, y_off, fsize, fcolor, bg_color in [
            ("tower", -0.55, 10, "#4A148C", "#F3E5F5"),
            ("waveform", -0.50, 9, "#880E4F", "#FCE4EC"),
            ("chester", -0.55, 9, "#E65100", "#FFF3E0"),
        ]:
            if node_id in pos:
                lx, ly = pos[node_id]
                label = G.nodes[node_id].get("label", node_id)
                ax.text(lx, ly + y_off, label,
                        fontsize=fsize, color=fcolor, fontweight="bold",
                        ha="center", va="top", rotation=0,
                        bbox=dict(boxstyle="round,pad=0.3",
                                  facecolor=bg_color, alpha=0.9,
                                  edgecolor=fcolor, linewidth=0.5))

        # Deco labels below nodes with background
        for n in deco_nodes:
            dx, dy = pos[n]
            label = G.nodes[n].get("label", n)
            ax.text(dx, dy - 0.45, label,
                    fontsize=9, color="#0f1a2a", fontweight="bold",
                    ha="center", va="top", rotation=0,
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="#E8F5E9", alpha=0.9,
                              edgecolor="#1E8B52", linewidth=0.5))

        # Device labels offset below
        device_labels = {}
        for n in online_devices + offline_devices:
            device_labels[n] = G.nodes[n].get("label", n)
        device_label_pos = {n: (pos[n][0], pos[n][1] - 0.30) for n in device_labels}
        nx.draw_networkx_labels(G, device_label_pos, labels=device_labels,
                                font_size=5.5, font_color="#37474F", ax=ax)

        # Legend
        legend_items = [
            mpatches.Patch(color="#9C27B0", label="T-Mobile Cell Tower"),
            mpatches.Patch(color="#E91E63", label="Waveform MIMO Antenna"),
            mpatches.Patch(color="#FF6F00", label="5G Chester Router"),
            mpatches.Patch(color="#1E8B52", label="Deco Mesh Node"),
            mpatches.Patch(color="#42A5F5", label="Device (Online)"),
            mpatches.Patch(color="#BDBDBD", label="Device (Offline)"),
            mpatches.Patch(color="#9C27B0", label="5G NR (Tower)"),
            mpatches.Patch(color="#FF9800", label="Mesh Backhaul"),
            mpatches.Patch(color="#1565C0", label="5 GHz WiFi"),
            mpatches.Patch(color="#2E7D32", label="2.4 GHz WiFi"),
            mpatches.Patch(color="#283593", label="6 GHz WiFi"),
            mpatches.Patch(color="#C62828", label="Wired"),
        ]
        ax.legend(handles=legend_items, loc="upper left", fontsize=7,
                  framealpha=0.9, fancybox=True, ncol=2)

        ax.set_title(f"Network Topology — {conn_type_str} | "
                     f"{len(deco_nodes)} Deco Nodes, "
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

        # 2026-03-13: Cache the SVG
        _topology_svg_cache = svg_data
        _topology_svg_cache_time = time.time()

        return Response(content=svg_data, media_type="image/svg+xml")

    except Exception as e:
        logger.error(f"Failed to generate topology graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate topology graph: {str(e)}")
