"""
Alexa Smart Home API Routes
Endpoints for Alexa device management, control, and OAuth
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
import os

import time
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alexa", tags=["alexa"])

# Global service references (injected from main.py)
alexa_service = None
alexa_client = None
deco_service = None
deco_client = None
chester_service = None
chester_client = None
db = None

# Discovery + state cache — Alexa enforces 8s timeout, Deco API takes 9-14s
_discovery_cache: Dict[str, Any] = {}
_discovery_cache_time: float = 0
_state_cache: Dict[str, Dict[str, Any]] = {}  # endpoint_id -> {properties}
_state_cache_time: float = 0
CACHE_TTL = 300  # 5 minutes


DEFAULT_ALEXA_REDIRECT_URI = "https://charissa-nonrefractional-dwana.ngrok-free.dev/api/alexa/auth/callback"


class AlexaAuthRequest(BaseModel):
    client_id: str
    client_secret: str
    allowed_origin: Optional[str] = None
    redirect_uri: Optional[str] = None


class DeviceCommand(BaseModel):
    command: str  # power_on, power_off, set_brightness, set_color, set_color_temperature, set_thermostat, set_thermostat_mode, lock, unlock
    params: Optional[Dict[str, Any]] = None
    pin: Optional[str] = None  # Required for unlock commands


class AlexaDeviceLink(BaseModel):
    network_device_id: str


def set_alexa_service(service):
    global alexa_service
    alexa_service = service


def set_alexa_client(client):
    global alexa_client
    alexa_client = client


def set_db(database):
    global db
    db = database


def set_deco_service(service):
    global deco_service
    deco_service = service


def set_deco_client(client):
    global deco_client
    deco_client = client


def set_chester_service(service):
    global chester_service
    chester_service = service


def set_chester_client(client):
    global chester_client
    chester_client = client


def _normalize_mac(mac: str) -> str:
    """Normalize MAC address for comparisons (aa:bb -> aabb)."""
    return "".join(ch for ch in (mac or "").lower() if ch.isalnum())


def _get_setting(key: str) -> Optional[str]:
    if db is None:
        return None
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def _set_setting(key: str, value: str):
    if db is None:
        return
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, value),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to set setting {key}: {e}")


def load_alexa_credentials_on_startup():
    """Load Alexa credentials — env vars take priority over DB.

    # 2026-03-10: Prefer env vars (ALEXA_CLIENT_ID, ALEXA_CLIENT_SECRET)
    # so secrets don't need to live in the database.
    """
    if alexa_client is None:
        return

    # Check env vars first
    env_id = os.getenv("ALEXA_CLIENT_ID", "")
    env_secret = os.getenv("ALEXA_CLIENT_SECRET", "")
    if env_id and env_secret:
        alexa_client.set_credentials(env_id, env_secret)
        logger.info("Loaded Alexa credentials from environment")
    elif db is not None:
        creds_json = _get_setting("alexa_credentials")
        if creds_json:
            try:
                creds = json.loads(creds_json)
                alexa_client.set_credentials(creds.get("client_id", ""), creds.get("client_secret", ""))
                logger.info("Loaded Alexa credentials from database")
            except Exception as e:
                logger.warning(f"Failed to load Alexa credentials: {e}")

    tokens_json = _get_setting("alexa_tokens")
    if tokens_json:
        try:
            tokens = json.loads(tokens_json)
            alexa_client.set_tokens(
                tokens.get("access_token", ""),
                tokens.get("refresh_token", ""),
                tokens.get("expires_in", 3600),
            )
        except Exception as e:
            logger.warning(f"Failed to load Alexa tokens: {e}")

    cookies_str = _get_setting("alexa_cookies")
    if cookies_str:
        try:
            alexa_client.set_cookies(cookies_str)
            logger.info("Alexa browser cookies loaded from DB")
        except Exception as e:
            logger.warning(f"Failed to load Alexa cookies: {e}")


def _get_oauth_config() -> Dict[str, str]:
    """Load Alexa OAuth web settings (origin + callback URL)."""
    config = {
        "allowed_origin": "https://localhost:8443",
        "redirect_uri": DEFAULT_ALEXA_REDIRECT_URI,
    }

    config_json = _get_setting("alexa_oauth_config")
    if not config_json:
        return config

    try:
        saved = json.loads(config_json)
        if saved.get("allowed_origin"):
            config["allowed_origin"] = saved["allowed_origin"]
        if saved.get("redirect_uri"):
            config["redirect_uri"] = saved["redirect_uri"]
    except Exception as e:
        logger.warning(f"Failed to parse Alexa OAuth config: {e}")

    return config


@router.get("/status")
async def get_alexa_status() -> Dict[str, Any]:
    """Get Alexa connection status"""
    if alexa_client is None:
        return {"configured": False, "authenticated": False, "cookies_set": False}

    return {
        "configured": bool(alexa_client.client_id and alexa_client.client_secret),
        "authenticated": alexa_client.is_authenticated(),
        "cookies_set": alexa_client.has_cookies(),
        "oauth_config": _get_oauth_config(),
    }


class CookieAuthRequest(BaseModel):
    cookies: str  # Raw cookie string from browser DevTools


@router.post("/cookies")
async def set_alexa_cookies(req: CookieAuthRequest) -> Dict[str, Any]:
    """Save browser cookies for Alexa web API access."""
    if alexa_client is None:
        raise HTTPException(status_code=500, detail="Alexa client not initialized")

    alexa_client.set_cookies(req.cookies)
    _set_setting("alexa_cookies", req.cookies)

    # Test the cookies
    result = alexa_client.test_cookies()
    return {
        "success": result.get("success", False),
        "message": f"Cookies saved. {result.get('customer_name', 'Unknown user')}" if result.get("success") else f"Cookies saved but test failed: {result.get('error', 'unknown')}",
        "test_result": result,
    }


@router.post("/cookies/test")
async def test_alexa_cookies() -> Dict[str, Any]:
    """Test if current cookies are valid."""
    if alexa_client is None:
        raise HTTPException(status_code=500, detail="Alexa client not initialized")
    return alexa_client.test_cookies()


@router.post("/auth")
async def start_alexa_auth(auth_req: AlexaAuthRequest) -> Dict[str, Any]:
    """Save Alexa OAuth credentials and return authorization URL"""
    if alexa_client is None:
        raise HTTPException(status_code=500, detail="Alexa client not initialized")

    alexa_client.set_credentials(auth_req.client_id, auth_req.client_secret)

    oauth_config = {
        "allowed_origin": auth_req.allowed_origin or "https://localhost:8443",
        "redirect_uri": auth_req.redirect_uri or DEFAULT_ALEXA_REDIRECT_URI,
    }

    # Save credentials
    _set_setting("alexa_credentials", json.dumps({
        "client_id": auth_req.client_id,
        "client_secret": auth_req.client_secret,
    }))
    _set_setting("alexa_oauth_config", json.dumps(oauth_config))

    redirect_uri = oauth_config["redirect_uri"]
    auth_url = alexa_client.get_auth_url(redirect_uri)

    return {
        "success": True,
        "auth_url": auth_url,
        "message": "Open the authorization URL to connect your Amazon account",
    }


@router.get("/auth/callback")
async def alexa_auth_callback(code: str = "", state: str = "") -> Dict[str, Any]:
    """Handle OAuth callback from Amazon"""
    if alexa_client is None:
        raise HTTPException(status_code=500, detail="Alexa client not initialized")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        redirect_uri = _get_oauth_config().get("redirect_uri", DEFAULT_ALEXA_REDIRECT_URI)
        token_data = alexa_client.exchange_code(code, redirect_uri)

        # Save tokens
        _set_setting("alexa_tokens", json.dumps({
            "access_token": token_data.get("access_token", ""),
            "refresh_token": token_data.get("refresh_token", ""),
            "expires_in": token_data.get("expires_in", 3600),
        }))

        return HTMLResponse(content="""
        <html><head><title>HomeSentinel - Alexa Connected</title>
        <style>body{font-family:system-ui;background:#1a1a2e;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
        .box{text-align:center;padding:40px;background:#16213e;border-radius:12px;border:1px solid #0f3460}
        h1{color:#4ecca3}p{color:#999}</style></head>
        <body><div class="box"><h1>Alexa Connected!</h1>
        <p>Your Amazon account is now linked to HomeSentinel.</p>
        <p>You can close this window and go to the Alexa tab to see your devices.</p>
        <script>setTimeout(()=>window.close(),5000)</script>
        </div></body></html>
        """)
    except Exception as e:
        return HTMLResponse(status_code=400, content=f"""
        <html><head><title>HomeSentinel - Error</title>
        <style>body{{font-family:system-ui;background:#1a1a2e;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
        .box{{text-align:center;padding:40px;background:#16213e;border-radius:12px;border:1px solid #e74c3c}}
        h1{{color:#e74c3c}}</style></head>
        <body><div class="box"><h1>Connection Failed</h1><p>{e}</p></div></body></html>
        """)


@router.get("/devices")
async def get_alexa_devices() -> Dict[str, Any]:
    """Get all Alexa devices with state"""
    if alexa_service is None:
        raise HTTPException(status_code=500, detail="Alexa service not initialized")

    try:
        devices = alexa_service.get_all_devices_with_state()

        link_map: Dict[str, str] = {}
        alexa_mac_map: Dict[str, str] = {}
        network_by_id: Dict[str, Dict[str, Any]] = {}
        network_by_mac: Dict[str, Dict[str, Any]] = {}
        network_by_ip: Dict[str, Dict[str, Any]] = {}
        network_by_alexa_name: Dict[str, Dict[str, Any]] = {}

        if db is not None:
            with db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT alexa_endpoint_id, network_device_id FROM alexa_device_links")
                for row in cursor.fetchall():
                    endpoint_id = row["alexa_endpoint_id"] if "alexa_endpoint_id" in row.keys() else row[0]
                    network_id = row["network_device_id"] if "network_device_id" in row.keys() else row[1]
                    link_map[str(endpoint_id)] = str(network_id)

                cursor.execute(
                    "SELECT endpoint_id, mac_address FROM alexa_devices "
                    "WHERE mac_address IS NOT NULL AND mac_address != ''"
                )
                for row in cursor.fetchall():
                    endpoint_id = row["endpoint_id"] if "endpoint_id" in row.keys() else row[0]
                    mac_address = row["mac_address"] if "mac_address" in row.keys() else row[1]
                    if endpoint_id and mac_address:
                        alexa_mac_map[str(endpoint_id)] = str(mac_address)

                cursor.execute(
                    "SELECT device_id, status, mac_address, current_ip, alexa_name "
                    "FROM network_devices"
                )
                for row in cursor.fetchall():
                    device = dict(row)
                    device_id = str(device.get("device_id", ""))
                    if not device_id:
                        continue
                    network_by_id[device_id] = device

                    mac_norm = _normalize_mac(str(device.get("mac_address") or ""))
                    if mac_norm and mac_norm not in network_by_mac:
                        network_by_mac[mac_norm] = device

                    ip = str(device.get("current_ip") or "").strip()
                    if ip and ip not in network_by_ip:
                        network_by_ip[ip] = device

                    alexa_name = str(device.get("alexa_name") or "").strip().lower()
                    if alexa_name and alexa_name not in network_by_alexa_name:
                        network_by_alexa_name[alexa_name] = device

        for device in devices:
            endpoint_id = str(device.get("endpoint_id", ""))
            matched_network: Optional[Dict[str, Any]] = None
            online_source = "alexa"

            linked_network_id = link_map.get(endpoint_id)
            if linked_network_id:
                matched_network = network_by_id.get(linked_network_id)
                if matched_network:
                    online_source = "deco"

            if matched_network is None:
                candidate_macs = []
                if device.get("mac_address"):
                    candidate_macs.append(str(device.get("mac_address")))
                if endpoint_id in alexa_mac_map:
                    candidate_macs.append(alexa_mac_map[endpoint_id])

                for candidate_mac in candidate_macs:
                    matched_network = network_by_mac.get(_normalize_mac(candidate_mac))
                    if matched_network:
                        online_source = "deco"
                        # Backfill for frontend visibility if mac came from DB.
                        device["mac_address"] = candidate_mac
                        break

            if matched_network is None:
                raw_data = device.get("raw_data") or {}
                candidate_ips = [
                    device.get("ip_address"),
                    device.get("current_ip"),
                    raw_data.get("ipAddress"),
                    raw_data.get("ip_address"),
                ]
                for candidate_ip in candidate_ips:
                    ip = str(candidate_ip or "").strip()
                    if not ip:
                        continue
                    matched_network = network_by_ip.get(ip)
                    if matched_network:
                        online_source = "deco"
                        break

            if matched_network is None:
                name_key = str(device.get("friendly_name") or "").strip().lower()
                if name_key:
                    matched_network = network_by_alexa_name.get(name_key)
                    if matched_network:
                        online_source = "deco"

            network_status = str(matched_network.get("status", "")) if matched_network else None
            is_online = (
                network_status == "online"
                if matched_network is not None
                else bool(device.get("is_reachable", not device.get("is_stale", True)))
            )

            device["network_status"] = network_status
            device["network_device_id"] = matched_network.get("device_id") if matched_network else None
            device["is_online"] = is_online
            device["online_source"] = online_source

        # Remove raw_data from response to keep it clean
        clean_devices = []
        for d in devices:
            device_copy = {k: v for k, v in d.items() if k != "raw_data"}
            clean_devices.append(device_copy)

        return {
            "devices": clean_devices,
            "total": len(clean_devices),
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get Alexa devices: {e}")
        if "Not authenticated" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Alexa")
        raise HTTPException(status_code=500, detail=f"Failed to get devices: {e}")


@router.get("/devices/{endpoint_id}")
async def get_alexa_device(endpoint_id: str) -> Dict[str, Any]:
    """Get a single Alexa device with current state"""
    if alexa_service is None:
        raise HTTPException(status_code=500, detail="Alexa service not initialized")

    try:
        device = alexa_service.get_device_with_state(endpoint_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        device_copy = {k: v for k, v in device.items() if k != "raw_data"}
        return {"device": device_copy}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get device: {e}")


@router.post("/devices/{endpoint_id}/command")
async def send_device_command(endpoint_id: str, cmd: DeviceCommand) -> Dict[str, Any]:
    """Send a command to an Alexa device"""
    if alexa_service is None:
        raise HTTPException(status_code=500, detail="Alexa service not initialized")

    # Unlock commands require PIN confirmation
    if cmd.command == "unlock" and not cmd.pin:
        raise HTTPException(status_code=400, detail="PIN required for unlock commands")

    try:
        result = alexa_service.send_command(endpoint_id, cmd.command, cmd.params)
        return {
            "success": True,
            "command": cmd.command,
            "endpoint_id": endpoint_id,
            "result": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Command failed: {e}")


@router.get("/echo-devices")
async def get_echo_devices() -> Dict[str, Any]:
    """Get Echo device inventory"""
    if alexa_service is None:
        raise HTTPException(status_code=500, detail="Alexa service not initialized")

    try:
        devices = alexa_service.get_echo_devices()
        clean_devices = [{k: v for k, v in d.items() if k != "raw_data"} for d in devices]
        return {
            "devices": clean_devices,
            "total": len(clean_devices),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Echo devices: {e}")


@router.post("/devices/{endpoint_id}/link")
async def link_alexa_to_network(endpoint_id: str, link: AlexaDeviceLink) -> Dict[str, Any]:
    """Manually link an Alexa device to a network device"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO alexa_device_links (alexa_endpoint_id, network_device_id, link_type) VALUES (?, ?, 'manual')",
                (endpoint_id, link.network_device_id),
            )
            conn.commit()
        return {"success": True, "message": "Devices linked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link devices: {e}")


@router.delete("/devices/{endpoint_id}/link/{network_device_id}")
async def unlink_alexa_from_network(endpoint_id: str, network_device_id: str) -> Dict[str, Any]:
    """Unlink an Alexa device from a network device"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM alexa_device_links WHERE alexa_endpoint_id = ? AND network_device_id = ?",
                (endpoint_id, network_device_id),
            )
            conn.commit()
        return {"success": True, "message": "Link removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlink devices: {e}")


@router.get("/links")
async def get_all_links() -> Dict[str, Any]:
    """Get all Alexa-to-network device links"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT al.alexa_endpoint_id, al.network_device_id, al.link_type,
                       ad.friendly_name as alexa_name, ad.device_type as alexa_type,
                       nd.mac_address, nd.current_ip, nd.friendly_name as network_name,
                       nd.vendor_name
                FROM alexa_device_links al
                LEFT JOIN alexa_devices ad ON al.alexa_endpoint_id = ad.endpoint_id
                LEFT JOIN network_devices nd ON al.network_device_id = nd.device_id
            """)
            rows = cursor.fetchall()
            links = [dict(row) for row in rows]
        return {"links": links, "total": len(links)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get links: {e}")


@router.get("/suggest-matches")
async def suggest_matches() -> Dict[str, Any]:
    """Suggest Alexa-to-network device matches based on vendor and device type"""
    if alexa_service is None or db is None:
        raise HTTPException(status_code=500, detail="Service not initialized")

    try:
        alexa_devices = alexa_service.get_devices()

        # Get network devices from DB
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT device_id, mac_address, current_ip, friendly_name,
                       vendor_name, hostname, status
                FROM network_devices
                ORDER BY status DESC, last_seen DESC
            """)
            network_devices = [dict(row) for row in cursor.fetchall()]

            # Get existing links
            cursor.execute("SELECT alexa_endpoint_id, network_device_id FROM alexa_device_links")
            existing_links = {row["alexa_endpoint_id"]: row["network_device_id"] for row in cursor.fetchall()}

        # Vendor-to-Alexa-type mapping for suggestions
        vendor_hints = {
            "amazon technologies inc.": ["echo", "tv"],
            "amazon": ["echo", "tv"],
            "espressif inc.": ["light", "plug", "sensor"],
            "espressif": ["light", "plug", "sensor"],
            "roku, inc": ["tv"],
            "roku": ["tv"],
            "alarm.com": ["security", "sensor", "lock"],
            "samsung": ["tv"],
            "google": ["tv"],
            "tp-link": ["plug"],
            "sonos": ["echo"],
            "ring": ["camera", "security"],
            "philips": ["light"],
            "signify": ["light"],
            "sengled": ["light"],
            "wyze": ["camera", "plug"],
            "ecobee": ["thermostat"],
            "honeywell": ["thermostat"],
        }

        suggestions = []
        for net_dev in network_devices:
            vendor = (net_dev.get("vendor_name") or "").lower()
            mac = net_dev.get("mac_address", "")
            device_id = net_dev.get("device_id", "")

            # Skip already-linked
            already_linked_to = None
            for alexa_id, nid in existing_links.items():
                if nid == device_id:
                    already_linked_to = alexa_id
                    break

            # Find matching Alexa device types for this vendor
            matching_types = []
            for vendor_key, types in vendor_hints.items():
                if vendor_key in vendor:
                    matching_types = types
                    break

            # Find Alexa devices that match
            candidates = []
            for alexa_dev in alexa_devices:
                alexa_id = alexa_dev.get("endpoint_id", "")
                if alexa_id in existing_links:
                    continue  # already linked to something else
                if matching_types and alexa_dev.get("device_type") in matching_types:
                    candidates.append({
                        "endpoint_id": alexa_id,
                        "friendly_name": alexa_dev.get("friendly_name", ""),
                        "device_type": alexa_dev.get("device_type", ""),
                        "confidence": "high" if len(matching_types) == 1 else "medium",
                    })

            suggestions.append({
                "network_device": {
                    "device_id": device_id,
                    "mac_address": mac,
                    "current_ip": net_dev.get("current_ip", ""),
                    "friendly_name": net_dev.get("friendly_name", ""),
                    "vendor_name": net_dev.get("vendor_name", ""),
                    "hostname": net_dev.get("hostname", ""),
                    "status": net_dev.get("status", ""),
                },
                "already_linked_to": already_linked_to,
                "suggested_alexa_devices": candidates,
            })

        # Also include unlinked Alexa devices
        unlinked_alexa = []
        for alexa_dev in alexa_devices:
            if alexa_dev.get("endpoint_id") not in existing_links:
                unlinked_alexa.append({
                    "endpoint_id": alexa_dev.get("endpoint_id", ""),
                    "friendly_name": alexa_dev.get("friendly_name", ""),
                    "device_type": alexa_dev.get("device_type", ""),
                    "description": alexa_dev.get("description", ""),
                })

        return {
            "suggestions": suggestions,
            "unlinked_alexa_devices": unlinked_alexa,
            "total_network": len(network_devices),
            "total_alexa": len(alexa_devices),
            "total_linked": len(existing_links),
        }
    except Exception as e:
        logger.error(f"Failed to suggest matches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suggest matches: {e}")


@router.post("/apply-name/{network_device_id}")
async def apply_alexa_name(network_device_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Apply an Alexa device name to a network device's friendly_name"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    new_name = body.get("friendly_name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="friendly_name is required")

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE network_devices SET friendly_name = ?, updated_at = CURRENT_TIMESTAMP WHERE device_id = ?",
                (new_name, network_device_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Network device not found")
        return {"success": True, "message": f"Device renamed to '{new_name}'"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename device: {e}")


# ─── Alexa Endpoint API MAC address import ─────────────────────────────────
# Uses the Alexa Endpoint API v2 with expand=all to pull connection objects
# containing MAC addresses. These are matched to network_devices by MAC.
# See: https://developer.amazon.com/en-US/docs/alexa/alexa-smart-properties/endpoint-api.html#connection-object

@router.post("/import-mac-addresses")
async def import_alexa_mac_addresses() -> Dict[str, Any]:
    """Pull MAC addresses from Alexa Echo/Fire devices and auto-link to network devices.

    # 2026-03-09: Rewritten to use /api/device-wifi-details as primary source.
    # Previous approaches (Endpoint API v2 connections[].macAddress and devices-v2 macAddress)
    # don't work for consumer accounts — Endpoint API returns 403 (needs ASP scope),
    # and devices-v2 macAddress field is always null.
    #
    # The undocumented /api/device-wifi-details endpoint (cookie-based, via alexapy discovery)
    # takes deviceSerialNumber + deviceType and returns the real WiFi MAC + ESSID
    # for physical Echo/Fire hardware. Groups and non-hardware entities return 400.
    # This successfully returns MACs for ~16 of ~30 devices (real hardware only).
    """
    if alexa_client is None:
        raise HTTPException(status_code=500, detail="Alexa client not initialized")

    # ── Primary source: /api/device-wifi-details (cookie-based, real hardware MACs) ──
    # Uses get_all_device_macs() which iterates devices-v2, calls device-wifi-details
    # for each, and returns normalized MAC addresses (aa:bb:cc:dd:ee:ff format).
    try:
        device_macs = alexa_client.get_all_device_macs()
    except Exception as e:
        logger.error(f"get_all_device_macs() failed: {e}")
        device_macs = []

    # Convert to endpoint_macs format: (identifier, friendly_name, mac_normalized, device_family)
    endpoint_macs = [
        (dm["serialNumber"], dm["accountName"], dm["macAddress"], dm.get("deviceFamily", ""))
        for dm in device_macs
        if dm.get("macAddress")
    ]

    # Count total devices attempted (from devices-v2 list)
    total_devices = 0
    try:
        raw_devices = alexa_client.get_echo_devices_web()
        total_devices = len(raw_devices) if raw_devices else 0
    except Exception:
        pass

    source = "device_wifi_details" if endpoint_macs else "none"
    logger.info(f"MAC import: source={source}, total_devices={total_devices}, with_mac={len(endpoint_macs)}")

    if not endpoint_macs:
        return {
            "success": True,
            "source": source,
            "total_endpoints": total_devices,
            "with_mac": 0,
            "linked": 0,
            "named": 0,
            "note": "No MAC addresses found. The /api/device-wifi-details endpoint "
                    "only returns MACs for physical Echo/Fire hardware. Ensure Alexa "
                    "cookies are configured. Use Deco import for non-Alexa device matching.",
            "endpoints": [],
        }

    linked = 0
    named = 0
    matched = 0  # MACs that match a network_device

    logger.info(f"MAC import: db={'set' if db else 'None'}, endpoint_macs={len(endpoint_macs)}")

    if db and endpoint_macs:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Ensure mac_address column exists on alexa_devices
            # (added by migration 007, but safe to ensure)
            try:
                cursor.execute("SELECT mac_address FROM alexa_devices LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE alexa_devices ADD COLUMN mac_address TEXT")

            for serial_or_id, friendly_name, mac, device_family in endpoint_macs:
                # Store MAC on alexa_devices record (match by endpoint_id which may be serial)
                # Note: endpoint_id in alexa_devices may differ from serial number used here,
                # so this UPDATE may affect 0 rows — that's fine.
                cursor.execute(
                    "UPDATE alexa_devices SET mac_address = ? WHERE endpoint_id = ?",
                    (mac, serial_or_id),
                )

                # Match to network device by MAC
                cursor.execute(
                    "SELECT device_id, friendly_name FROM network_devices WHERE mac_address = ?",
                    (mac,),
                )
                row = cursor.fetchone()
                if not row:
                    logger.debug(f"No network device match for MAC {mac} ({friendly_name})")
                    continue

                net_device_id = row[0]
                net_friendly_name = row[1]
                matched += 1
                logger.info(f"MAC match: {mac} ({friendly_name}) -> network device {net_device_id} ({net_friendly_name})")

                # 2026-03-09: Write alexa_name and alexa_device_type to network_devices
                # (always overwrite with latest Alexa data)
                cursor.execute(
                    "UPDATE network_devices SET alexa_name = ?, alexa_device_type = ? WHERE device_id = ?",
                    (friendly_name, device_family, net_device_id),
                )

                # Auto-create link if the alexa device exists in DB
                # (serial_or_id may not match an alexa_devices.endpoint_id, so check first
                # to avoid FK constraint violations on alexa_device_links)
                cursor.execute(
                    "SELECT 1 FROM alexa_devices WHERE endpoint_id = ?",
                    (serial_or_id,),
                )
                if cursor.fetchone():
                    cursor.execute(
                        "INSERT OR IGNORE INTO alexa_device_links (alexa_endpoint_id, network_device_id, link_type) VALUES (?, ?, 'auto')",
                        (serial_or_id, net_device_id),
                    )
                    if cursor.rowcount > 0:
                        linked += 1

                # Apply Alexa name to network devices that are unnamed or have
                # generic names (e.g. "Amazon", "network device", "phone").
                # Alexa names like "Kitchen Echo" are more descriptive.
                generic_names = {"amazon", "network device", "phone", "unknown", "", None}
                if friendly_name and (net_friendly_name or "").lower().strip() in generic_names:
                    cursor.execute(
                        "UPDATE network_devices SET friendly_name = ? WHERE device_id = ?",
                        (friendly_name, net_device_id),
                    )
                    if cursor.rowcount > 0:
                        named += 1
                        logger.info(f"Named device {net_device_id}: '{net_friendly_name}' -> '{friendly_name}'")

            conn.commit()

    return {
        "success": True,
        "source": source,
        "total_endpoints": total_devices,
        "with_mac": len(endpoint_macs),
        "matched": matched,
        "linked": linked,
        "named": named,
        "endpoints": [
            {"endpoint_id": serial_or_id, "friendly_name": name, "mac_address": mac, "device_family": family}
            for serial_or_id, name, mac, family in endpoint_macs
        ],
    }


# ─── Lambda-facing endpoints ───────────────────────────────────────────────
# DISABLED 2026-03-09: All Lambda↔local endpoints return 503.
# These were exposing unauthenticated device discovery, state, and control
# (WiFi toggle, reboot, etc.) to anyone who could reach the backend URL.
# The Lambda function in lambda/lambda_function.py calls these endpoints —
# until proper API key auth is added, they stay disabled.
# Original implementations are preserved below each stub for re-enablement.

class LambdaTokenRequest(BaseModel):
    access_token: str


class LambdaAcceptGrantRequest(BaseModel):
    auth_code: str
    access_token: Optional[str] = None


class LambdaCommandRequest(BaseModel):
    endpoint_id: str
    namespace: Optional[str] = None
    instance: Optional[str] = None
    name: Optional[str] = None
    command: str
    value: Any


@router.post("/lambda/token")
async def lambda_store_token(req: LambdaTokenRequest) -> Dict[str, Any]:
    """Receive and store bearer token forwarded from the Lambda."""
    raise HTTPException(status_code=503, detail="Lambda integration is disabled")


@router.post("/lambda/accept-grant")
async def lambda_accept_grant(req: LambdaAcceptGrantRequest) -> Dict[str, Any]:
    """Handle AcceptGrant - exchange auth code for long-lived tokens."""
    raise HTTPException(status_code=503, detail="Lambda integration is disabled")


# ─── Alexa Smart Home Discovery ───────────────────────────────────────────────

def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _cap_alexa():
    return {"type": "AlexaInterface", "interface": "Alexa", "version": "3"}


def _cap_health():
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.EndpointHealth",
        "version": "3",
        "properties": {
            "supported": [{"name": "connectivity"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
    }


def _cap_power():
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.PowerController",
        "version": "3",
        "properties": {
            "supported": [{"name": "powerState"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
    }


def _cap_toggle(instance: str, friendly_name: str):
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.ToggleController",
        "version": "3",
        "instance": instance,
        "properties": {
            "supported": [{"name": "toggleState"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
        "capabilityResources": {
            "friendlyNames": [
                {"@type": "text", "value": {"text": friendly_name, "locale": "en-US"}},
            ],
        },
    }


def _cap_range(instance: str, friendly_name: str, min_v: int, max_v: int, read_only: bool = True):
    cap = {
        "type": "AlexaInterface",
        "interface": "Alexa.RangeController",
        "version": "3",
        "instance": instance,
        "properties": {
            "supported": [{"name": "rangeValue"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
        "capabilityResources": {
            "friendlyNames": [
                {"@type": "text", "value": {"text": friendly_name, "locale": "en-US"}},
            ],
        },
        "configuration": {
            "supportedRange": {"minimumValue": min_v, "maximumValue": max_v, "precision": 1},
        },
    }
    if read_only:
        cap["properties"]["nonControllable"] = True
    return cap


def _cap_mode(instance: str, friendly_name: str, modes: Dict[str, str]):
    supported_modes = []
    for mode_val, mode_name in modes.items():
        supported_modes.append({
            "value": mode_val,
            "modeResources": {
                "friendlyNames": [
                    {"@type": "text", "value": {"text": mode_name, "locale": "en-US"}},
                ],
            },
        })
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.ModeController",
        "version": "3",
        "instance": instance,
        "properties": {
            "supported": [{"name": "mode"}],
            "proactivelyReported": False,
            "retrievable": True,
            "nonControllable": True,
        },
        "capabilityResources": {
            "friendlyNames": [
                {"@type": "text", "value": {"text": friendly_name, "locale": "en-US"}},
            ],
        },
        "configuration": {"ordered": False, "supportedModes": supported_modes},
    }


def _cap_scene(deactivation: bool = False):
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.SceneController",
        "version": "3",
        "supportsDeactivation": deactivation,
        "proactivelyReported": False,
    }


def _build_deco_endpoints() -> List[Dict[str, Any]]:
    """Build Alexa endpoints from Deco mesh data."""
    endpoints = []
    if deco_client is None:
        return endpoints

    try:
        if not deco_client.is_authenticated():
            deco_client.authenticate()
    except Exception as e:
        logger.warning(f"Deco auth failed during discovery: {e}")
        return endpoints

    # ── Deco WiFi Control endpoint (virtual device for WiFi management) ──
    endpoints.append({
        "endpointId": "deco-wifi-control",
        "manufacturerName": "TP-Link",
        "friendlyName": "Deco WiFi",
        "description": "TP-Link Deco mesh WiFi network controls",
        "displayCategories": ["SWITCH"],
        "capabilities": [
            _cap_alexa(),
            _cap_health(),
            _cap_power(),  # Main WiFi on/off (all bands)
            _cap_toggle("GuestWiFi", "Guest WiFi"),
            _cap_toggle("IoTNetwork", "IoT Network"),
            _cap_toggle("WiFi24", "2.4 GHz WiFi"),
            _cap_toggle("WiFi5", "5 GHz WiFi"),
            _cap_toggle("WiFi6", "6 GHz WiFi"),
        ],
    })

    # ── Network Reboot scene ──
    endpoints.append({
        "endpointId": "deco-reboot",
        "manufacturerName": "TP-Link",
        "friendlyName": "Network Reboot",
        "description": "Reboot the Deco mesh network",
        "displayCategories": ["SCENE_TRIGGER"],
        "capabilities": [
            _cap_alexa(),
            _cap_scene(deactivation=False),
        ],
    })

    # ── Individual Deco nodes ──
    try:
        nodes = deco_client.get_device_list()
    except Exception as e:
        logger.warning(f"Failed to get Deco nodes for discovery: {e}")
        nodes = []

    for node in nodes:
        mac = node.get("mac", "").replace("-", ":").replace(":", "").lower()
        nickname = node.get("nickname", node.get("alias", node.get("name", f"Deco {mac[-4:]}")))
        role = node.get("role", "slave")
        model = node.get("device_model", "Deco")
        fw = node.get("software_ver", "")
        ip = node.get("device_ip", "")

        endpoint_id = f"deco-node-{mac}" if mac else f"deco-node-{nickname.lower().replace(' ', '-')}"

        caps = [_cap_alexa(), _cap_health()]

        # Signal strength sensor for satellite nodes
        if role != "master":
            signal_2g = node.get("signal_strength", {}).get("band2_4")
            signal_5g = node.get("signal_strength", {}).get("band5")
            if signal_2g is not None or signal_5g is not None:
                caps.append(_cap_range("SignalStrength", "Signal Strength", -100, 0, read_only=True))

        # Connection type mode
        conn_types = node.get("connection_type", [])
        if conn_types:
            modes = {}
            for ct in conn_types:
                modes[ct] = ct.replace("_", " ").title()
            caps.append(_cap_mode("ConnectionType", "Connection Type", modes))

        endpoints.append({
            "endpointId": endpoint_id,
            "manufacturerName": "TP-Link",
            "friendlyName": f"Deco {nickname}",
            "description": f"TP-Link {model} mesh node ({role}) - {ip} - FW {fw}",
            "displayCategories": ["SWITCH"],
            "capabilities": caps,
            "cookie": {
                "mac": node.get("mac", ""),
                "role": role,
                "model": model,
                "ip": ip,
            },
        })

    # ── Connected clients count as a sensor ──
    try:
        clients = deco_client.get_client_list()
        online_count = sum(1 for c in clients if c.get("online"))
    except Exception:
        online_count = 0

    endpoints.append({
        "endpointId": "deco-client-count",
        "manufacturerName": "HomeSentinel",
        "friendlyName": "Connected Devices",
        "description": f"Number of devices connected to the network ({online_count} online)",
        "displayCategories": ["SWITCH"],
        "capabilities": [
            _cap_alexa(),
            _cap_health(),
            _cap_range("ClientCount", "Connected Devices", 0, 200, read_only=True),
        ],
    })

    return endpoints


def _build_chester_endpoints() -> List[Dict[str, Any]]:
    """Build Alexa endpoints from Chester 5G router data."""
    endpoints = []
    if chester_client is None:
        return endpoints

    try:
        if not chester_client.is_authenticated():
            chester_client.authenticate()
    except Exception:
        pass

    endpoints.append({
        "endpointId": "chester-router",
        "manufacturerName": "Chester",
        "friendlyName": "5G Router",
        "description": "Chester 5G Wireless Data Terminal",
        "displayCategories": ["SWITCH"],
        "capabilities": [
            _cap_alexa(),
            _cap_health(),
            _cap_range("SignalStrength", "Signal Strength", 0, 100, read_only=True),
            _cap_mode("ConnectionType", "Connection Type", {
                "5G": "5G",
                "LTE": "LTE",
                "3G": "3G",
                "disconnected": "Disconnected",
            }),
        ],
    })

    return endpoints


@router.get("/lambda/discover")
async def lambda_discover() -> Dict[str, Any]:
    """Return cached Alexa endpoints. Alexa enforces 8s timeout so we must respond fast."""
    raise HTTPException(status_code=503, detail="Lambda integration is disabled")


@router.post("/lambda/refresh-cache")
async def lambda_refresh_cache() -> Dict[str, Any]:
    """Refresh discovery + state caches (called by Lambda warmup every 5 min)."""
    raise HTTPException(status_code=503, detail="Lambda integration is disabled")


async def _refresh_state_cache():
    """Build state cache for all known endpoints."""
    global _state_cache, _state_cache_time
    ts = _utc_now()
    states = {}

    # All nodes are ON if they appear in device list
    node_statuses = {}
    try:
        if deco_client:
            if not deco_client.is_authenticated():
                deco_client.authenticate()
            nodes = deco_client.get_device_list()
            for n in nodes:
                mac = n.get("mac", "").replace("-", ":").replace(":", "").lower()
                node_statuses[f"deco-node-{mac}"] = n.get("inet_status", "") == "online"
    except Exception as e:
        logger.warning(f"State cache: Deco node list failed: {e}")

    # WiFi state
    wifi_on = True
    try:
        if deco_client:
            wifi = deco_client.get_wifi_settings()
            h24 = wifi.get("band2_4", {}).get("host", {}).get("enable", False)
            h5 = wifi.get("band5_1", {}).get("host", {}).get("enable", False)
            h6 = wifi.get("band6", {}).get("host", {}).get("enable", False)
            wifi_on = h24 or h5 or h6
    except Exception:
        pass

    def _on_state(is_on):
        return {"properties": [
            {"namespace": "Alexa.PowerController", "name": "powerState",
             "value": "ON" if is_on else "OFF", "timeOfSample": ts, "uncertaintyInMilliseconds": 500},
            {"namespace": "Alexa.EndpointHealth", "name": "connectivity",
             "value": {"value": "OK"}, "timeOfSample": ts, "uncertaintyInMilliseconds": 500},
        ]}

    states["deco-wifi-control"] = _on_state(wifi_on)
    states["deco-reboot"] = {"properties": [
        {"namespace": "Alexa.EndpointHealth", "name": "connectivity",
         "value": {"value": "OK"}, "timeOfSample": ts, "uncertaintyInMilliseconds": 0},
    ]}
    states["deco-client-count"] = _on_state(True)

    for eid, online in node_statuses.items():
        states[eid] = _on_state(online)

    # Chester
    chester_on = False
    try:
        chester_on = chester_client is not None and chester_client.is_authenticated()
    except Exception:
        pass
    states["chester-router"] = _on_state(chester_on)

    _state_cache = states
    _state_cache_time = time.time()


async def _build_all_endpoints() -> Dict[str, Any]:
    """Build Alexa-compatible endpoints using proven SWITCH/SCENE_TRIGGER format."""
    _power = {
        "type": "AlexaInterface", "interface": "Alexa.PowerController", "version": "3",
        "properties": {"supported": [{"name": "powerState"}], "proactivelyReported": False, "retrievable": True},
    }
    _alexa = {"type": "AlexaInterface", "interface": "Alexa", "version": "3"}

    def _switch(eid, name, desc):
        return {"endpointId": eid, "manufacturerName": "HomeSentinel", "friendlyName": name,
                "description": desc, "displayCategories": ["SWITCH"], "capabilities": [_alexa, _power]}

    endpoints = [
        # WiFi control — main controllable device
        _switch("deco-wifi-control", "Deco WiFi", "WiFi network control"),
        # Reboot scene
        {
            "endpointId": "deco-reboot",
            "manufacturerName": "HomeSentinel",
            "friendlyName": "Network Reboot",
            "description": "Reboot the Deco mesh network",
            "displayCategories": ["SCENE_TRIGGER"],
            "capabilities": [
                _alexa,
                {"type": "AlexaInterface", "interface": "Alexa.SceneController", "version": "3",
                 "supportsDeactivation": False, "proactivelyReported": False},
            ],
        },
    ]

    # Deco nodes as switches (on = online monitoring)
    try:
        if deco_client and deco_client.is_authenticated():
            nodes = deco_client.get_device_list()
        elif deco_client:
            deco_client.authenticate()
            nodes = deco_client.get_device_list()
        else:
            nodes = []
    except Exception as e:
        logger.warning(f"Deco node discovery failed: {e}")
        nodes = []

    for node in nodes:
        mac = node.get("mac", "").replace("-", ":").replace(":", "").lower()
        nickname = node.get("nickname", node.get("alias", node.get("name", f"Node {mac[-4:]}")))
        role = node.get("role", "slave")
        ip = node.get("device_ip", "")
        eid = f"deco-node-{mac}" if mac else f"deco-node-{nickname.lower().replace(' ', '-')}"
        endpoints.append(_switch(eid, f"Deco {nickname}", f"Deco mesh node ({role}) at {ip}"))

    # Connected devices count
    endpoints.append(_switch("deco-client-count", "Connected Devices", "Network client count"))

    # Chester 5G router
    if chester_client:
        endpoints.append(_switch("chester-router", "5G Router", "Chester 5G wireless router"))

    return {"endpoints": endpoints}


# ─── State Reporting ──────────────────────────────────────────────────────────

@router.get("/lambda/state/{endpoint_id}")
async def lambda_get_state(endpoint_id: str) -> Dict[str, Any]:
    """Return cached device state for Alexa ReportState."""
    raise HTTPException(status_code=503, detail="Lambda integration is disabled")


async def _get_deco_wifi_state(ts: str) -> Dict[str, Any]:
    """Get WiFi network state from Deco."""
    properties = []
    try:
        wifi = deco_client.get_wifi_settings()

        # Main WiFi power state (any host band enabled = ON)
        host_24 = wifi.get("band2_4", {}).get("host", {}).get("enable", False)
        host_5 = wifi.get("band5_1", {}).get("host", {}).get("enable", False)
        host_6 = wifi.get("band6", {}).get("host", {}).get("enable", False)
        any_on = host_24 or host_5 or host_6

        properties.append({
            "namespace": "Alexa.PowerController", "name": "powerState",
            "value": "ON" if any_on else "OFF",
            "timeOfSample": ts, "uncertaintyInMilliseconds": 500,
        })

        # Guest WiFi toggle
        guest_24 = wifi.get("band2_4", {}).get("guest", {}).get("enable", False)
        guest_5 = wifi.get("band5_1", {}).get("guest", {}).get("enable", False)
        guest_6 = wifi.get("band6", {}).get("guest", {}).get("enable", False)
        properties.append({
            "namespace": "Alexa.ToggleController", "instance": "GuestWiFi",
            "name": "toggleState", "value": "ON" if (guest_24 or guest_5 or guest_6) else "OFF",
            "timeOfSample": ts, "uncertaintyInMilliseconds": 500,
        })

        # IoT network toggle
        iot_enabled = wifi.get("iot", {}).get("host", {}).get("enable", False)
        properties.append({
            "namespace": "Alexa.ToggleController", "instance": "IoTNetwork",
            "name": "toggleState", "value": "ON" if iot_enabled else "OFF",
            "timeOfSample": ts, "uncertaintyInMilliseconds": 500,
        })

        # Per-band toggles
        for band_key, instance in [("band2_4", "WiFi24"), ("band5_1", "WiFi5"), ("band6", "WiFi6")]:
            enabled = wifi.get(band_key, {}).get("host", {}).get("enable", False)
            properties.append({
                "namespace": "Alexa.ToggleController", "instance": instance,
                "name": "toggleState", "value": "ON" if enabled else "OFF",
                "timeOfSample": ts, "uncertaintyInMilliseconds": 500,
            })

        properties.append({
            "namespace": "Alexa.EndpointHealth", "name": "connectivity",
            "value": {"value": "OK"}, "timeOfSample": ts, "uncertaintyInMilliseconds": 500,
        })

    except Exception as e:
        logger.error(f"Deco WiFi state failed: {e}")
        properties.append({
            "namespace": "Alexa.EndpointHealth", "name": "connectivity",
            "value": {"value": "UNREACHABLE"}, "timeOfSample": ts,
            "uncertaintyInMilliseconds": 0,
        })

    return {"properties": properties}


async def _get_deco_client_count_state(ts: str) -> Dict[str, Any]:
    """Get connected client count from Deco."""
    properties = []
    try:
        clients = deco_client.get_client_list()
        online = sum(1 for c in clients if c.get("online"))
        properties.append({
            "namespace": "Alexa.RangeController", "instance": "ClientCount",
            "name": "rangeValue", "value": online,
            "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
        })
        properties.append({
            "namespace": "Alexa.EndpointHealth", "name": "connectivity",
            "value": {"value": "OK"}, "timeOfSample": ts, "uncertaintyInMilliseconds": 500,
        })
    except Exception as e:
        logger.error(f"Client count state failed: {e}")
        properties.append({
            "namespace": "Alexa.EndpointHealth", "name": "connectivity",
            "value": {"value": "UNREACHABLE"}, "timeOfSample": ts,
            "uncertaintyInMilliseconds": 0,
        })
    return {"properties": properties}


async def _get_deco_node_state(endpoint_id: str, ts: str) -> Dict[str, Any]:
    """Get state for a specific Deco node."""
    properties = []
    mac_suffix = endpoint_id.replace("deco-node-", "")

    try:
        nodes = deco_client.get_device_list()
        node = None
        for n in nodes:
            node_mac = n.get("mac", "").replace("-", ":").replace(":", "").lower()
            if node_mac == mac_suffix:
                node = n
                break

        if node:
            is_online = node.get("inet_status") == "online" or node.get("group_status") == "connected"
            properties.append({
                "namespace": "Alexa.EndpointHealth", "name": "connectivity",
                "value": {"value": "OK" if is_online else "UNREACHABLE"},
                "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
            })

            # Signal strength for satellites
            signal = node.get("signal_strength", {})
            best_signal = None
            for band in ["band5", "band2_4", "band6"]:
                val = signal.get(band)
                if val is not None:
                    if best_signal is None or val > best_signal:
                        best_signal = val
            if best_signal is not None:
                properties.append({
                    "namespace": "Alexa.RangeController", "instance": "SignalStrength",
                    "name": "rangeValue", "value": best_signal,
                    "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
                })

            # Connection type
            conn_types = node.get("connection_type", [])
            if conn_types:
                properties.append({
                    "namespace": "Alexa.ModeController", "instance": "ConnectionType",
                    "name": "mode", "value": conn_types[0],
                    "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
                })
        else:
            properties.append({
                "namespace": "Alexa.EndpointHealth", "name": "connectivity",
                "value": {"value": "UNREACHABLE"}, "timeOfSample": ts,
                "uncertaintyInMilliseconds": 0,
            })

    except Exception as e:
        logger.error(f"Deco node state failed for {endpoint_id}: {e}")
        properties.append({
            "namespace": "Alexa.EndpointHealth", "name": "connectivity",
            "value": {"value": "UNREACHABLE"}, "timeOfSample": ts,
            "uncertaintyInMilliseconds": 0,
        })

    return {"properties": properties}


async def _get_chester_state(ts: str) -> Dict[str, Any]:
    """Get Chester 5G router state."""
    properties = []
    try:
        if chester_service:
            status = chester_service.get_router_status()
            is_online = status.get("status") == "connected" or bool(status.get("board"))
            properties.append({
                "namespace": "Alexa.EndpointHealth", "name": "connectivity",
                "value": {"value": "OK" if is_online else "UNREACHABLE"},
                "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
            })

            # Signal strength from wireless status
            wireless = status.get("wireless", {})
            signal = wireless.get("signal_strength") or wireless.get("rssi")
            if signal is not None:
                # Normalize to 0-100 if needed
                if isinstance(signal, (int, float)) and signal < 0:
                    signal = max(0, min(100, 2 * (signal + 100)))  # dBm to percentage
                properties.append({
                    "namespace": "Alexa.RangeController", "instance": "SignalStrength",
                    "name": "rangeValue", "value": int(signal),
                    "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
                })

            # Connection type
            conn_type = wireless.get("network_type") or wireless.get("mode")
            if conn_type:
                properties.append({
                    "namespace": "Alexa.ModeController", "instance": "ConnectionType",
                    "name": "mode", "value": conn_type,
                    "timeOfSample": ts, "uncertaintyInMilliseconds": 6000,
                })
        else:
            properties.append({
                "namespace": "Alexa.EndpointHealth", "name": "connectivity",
                "value": {"value": "UNREACHABLE"}, "timeOfSample": ts,
                "uncertaintyInMilliseconds": 0,
            })
    except Exception as e:
        logger.error(f"Chester state failed: {e}")
        properties.append({
            "namespace": "Alexa.EndpointHealth", "name": "connectivity",
            "value": {"value": "UNREACHABLE"}, "timeOfSample": ts,
            "uncertaintyInMilliseconds": 0,
        })

    return {"properties": properties}


# ─── Command Handling ─────────────────────────────────────────────────────────

@router.post("/lambda/command")
async def lambda_command(req: LambdaCommandRequest) -> Dict[str, Any]:
    """Handle commands forwarded from the Lambda.

    Dispatches to Deco/Chester based on endpoint_id and namespace.
    """
    raise HTTPException(status_code=503, detail="Lambda integration is disabled")


async def _handle_deco_wifi_command(req: LambdaCommandRequest) -> Dict[str, Any]:
    """Handle WiFi control commands via Deco local API."""
    if deco_client is None:
        return {"success": False, "error": "Deco client not available"}

    # Map toggle instances to WiFi band operations
    instance = req.instance or ""
    is_on = req.value in ("ON", "TurnOn", True, "true")

    try:
        if req.namespace == "Alexa.PowerController":
            # Main WiFi power - toggle all host bands
            wifi = deco_client.get_wifi_settings()
            params = {}
            for band_key in ["band2_4", "band5_1", "band6"]:
                band = wifi.get(band_key, {})
                if "host" in band:
                    if band_key not in params:
                        params[band_key] = {}
                    params[band_key]["host"] = {"enable": is_on}

            _deco_wifi_write(params)
            return {"success": True, "message": f"All WiFi bands {'enabled' if is_on else 'disabled'}"}

        if req.namespace == "Alexa.ToggleController":
            if instance == "GuestWiFi":
                wifi = deco_client.get_wifi_settings()
                params = {}
                for band_key in ["band2_4", "band5_1", "band6"]:
                    band = wifi.get(band_key, {})
                    if "guest" in band:
                        if band_key not in params:
                            params[band_key] = {}
                        params[band_key]["guest"] = {"enable": is_on}
                _deco_wifi_write(params)
                return {"success": True, "message": f"Guest WiFi {'enabled' if is_on else 'disabled'}"}

            if instance == "IoTNetwork":
                _deco_wifi_write({"iot": {"host": {"enable": is_on}}})
                return {"success": True, "message": f"IoT network {'enabled' if is_on else 'disabled'}"}

            band_map = {"WiFi24": "band2_4", "WiFi5": "band5_1", "WiFi6": "band6"}
            band_key = band_map.get(instance)
            if band_key:
                _deco_wifi_write({band_key: {"host": {"enable": is_on}}})
                return {"success": True, "message": f"{instance} {'enabled' if is_on else 'disabled'}"}

        return {"success": True, "message": f"Unhandled WiFi command: {req.namespace}.{instance}"}

    except Exception as e:
        logger.error(f"Deco WiFi command failed: {e}")
        return {"success": False, "error": str(e)}


def _deco_wifi_write(params: Dict[str, Any]):
    """Write WiFi settings to Deco via encrypted local API."""
    if deco_client is None:
        raise RuntimeError("Deco client not available")

    if not deco_client.use_cloud and hasattr(deco_client, '_local_encrypted_request'):
        import json as _json
        deco_client._local_encrypted_request(
            "admin/wireless?form=wlan",
            _json.dumps({"operation": "write", "params": params})
        )
    else:
        logger.warning("WiFi write requires local Deco API (cloud passthrough not supported)")
        raise RuntimeError("WiFi control requires local Deco connection")


async def _handle_deco_reboot(req: LambdaCommandRequest) -> Dict[str, Any]:
    """Handle Deco network reboot via local API."""
    if deco_client is None:
        return {"success": False, "error": "Deco client not available"}

    try:
        if not deco_client.use_cloud and hasattr(deco_client, '_local_encrypted_request'):
            import json as _json
            nodes = deco_client.get_device_list()
            mac_list = [{"mac": n.get("mac", "")} for n in nodes if n.get("mac")]
            deco_client._local_encrypted_request(
                "admin/device?form=system",
                _json.dumps({"operation": "reboot", "params": {"mac_list": mac_list}})
            )
            return {"success": True, "message": f"Rebooting {len(mac_list)} Deco nodes"}
        else:
            return {"success": False, "error": "Reboot requires local Deco connection"}
    except Exception as e:
        logger.error(f"Deco reboot failed: {e}")
        return {"success": False, "error": str(e)}


def _map_device_type(device_type: Optional[str]) -> str:
    """Map HomeSentinel device types to Alexa display categories."""
    mapping = {
        "router": "NETWORK_HARDWARE",
        "switch": "SWITCH",
        "camera": "CAMERA",
        "speaker": "SPEAKER",
        "tv": "TV",
        "light": "LIGHT",
        "thermostat": "THERMOSTAT",
        "plug": "SMARTPLUG",
        "phone": "PHONE",
        "computer": "COMPUTER",
        "tablet": "TABLET",
    }
    return mapping.get((device_type or "").lower(), "OTHER")
