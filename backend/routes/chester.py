"""
Chester 5G Router API routes.

2026-03-11: Added /system-info endpoint for full cellular signal data.
2026-05-11: Added /static-ip for per-device DHCP reservations.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from services.chester_client import ChesterAPIError, ChesterAuthError
from utils import normalize_mac

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chester", tags=["chester"])

chester_client = None
chester_service = None
device_repo = None


def set_chester_client(client):
    global chester_client
    chester_client = client


def set_chester_service(service):
    global chester_service
    chester_service = service


def set_device_repo(repo):
    """Wire the network-device repository so we can persist toggle state."""
    global device_repo
    device_repo = repo


@router.get("/status")
async def get_chester_status() -> Dict[str, Any]:
    if chester_service is None:
        raise HTTPException(status_code=500, detail="Chester service not initialized")
    try:
        return chester_service.get_router_status()
    except ChesterAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ChesterAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/cellular")
async def get_chester_cellular() -> Dict[str, Any]:
    if chester_service is None:
        raise HTTPException(status_code=500, detail="Chester service not initialized")
    try:
        return chester_service.get_cellular_status()
    except ChesterAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ChesterAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# 2026-03-11: Full system info matching Chester web UI home page
@router.get("/system-info")
async def get_chester_system_info() -> Dict[str, Any]:
    """Get full Chester system and cellular signal info.

    Returns all fields shown on the Chester web UI status page:
    Device Model, System Version, Hardware Version, IMEI, ICCID,
    IPv4/IPv6 addresses, DNS, Connection Time/Type, CellID, PCID,
    ARFCN, BAND, RSRP, RSRQ, SINR, CA BAND, MCC, MNC.
    """
    if chester_service is None:
        raise HTTPException(status_code=500, detail="Chester service not initialized")
    try:
        return chester_service.get_system_info()
    except ChesterAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ChesterAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/band-config")
async def get_chester_band_config() -> Dict[str, Any]:
    """Get band lock configuration."""
    if chester_service is None:
        raise HTTPException(status_code=500, detail="Chester service not initialized")
    try:
        return chester_service.get_lte_band_config()
    except ChesterAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ChesterAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/traffic")
async def get_chester_traffic() -> Dict[str, Any]:
    """Get LTE data usage / traffic statistics."""
    if chester_service is None:
        raise HTTPException(status_code=500, detail="Chester service not initialized")
    try:
        return chester_service.get_lte_traffic_stats()
    except ChesterAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ChesterAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# 2026-05-11: Toggle per-device static DHCP reservation on the Chester router.
# Mirrors the DecoMesh client-mesh toggle pattern: optimistic UI, idempotent
# backend write, state persisted to network_devices.static_ip_enabled.
@router.post("/static-ip")
async def set_static_ip(request: Request) -> Dict[str, Any]:
    """Toggle a static DHCP reservation for a specific device.

    Request body:
        - mac_address (str, required): device MAC in any common format
        - enabled (bool, required): True to pin the IP, False to release it
        - reserved_ip (str, optional): IP to reserve. Defaults to the device's
          current_ip from our database (the "pin what it has now" workflow).

    Returns:
        - success (bool)
        - mac_address (str, normalized)
        - reserved_ip (str | None)
        - enabled (bool)
        - method (str): which mechanism actually wrote the lease
        - error_code (int)
        - detail (str)
    """
    if chester_client is None:
        raise HTTPException(status_code=500, detail="Chester client not initialized")
    if device_repo is None:
        raise HTTPException(status_code=500, detail="Device repository not initialized")

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}") from e

    raw_mac = body.get("mac_address")
    enabled = body.get("enabled")
    reserved_ip = body.get("reserved_ip")

    if not raw_mac or enabled is None:
        raise HTTPException(
            status_code=400,
            detail="mac_address and enabled are required",
        )

    try:
        mac_norm = normalize_mac(raw_mac)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    device = device_repo.get_by_mac(mac_norm)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device {mac_norm} not found")

    # Default to the device's currently observed IP — the "pin what it has now" flow.
    if enabled and not reserved_ip:
        reserved_ip = device.get("current_ip")
    if enabled and not reserved_ip:
        raise HTTPException(
            status_code=400,
            detail="Device has no current IP — wait for it to come online or pass reserved_ip explicitly",
        )

    hostname = (
        device.get("friendly_name")
        or device.get("hostname")
        or device.get("deco_name")
        or ""
    )

    try:
        result = chester_client.set_static_lease(
            mac_address=mac_norm,
            ip_address=reserved_ip or "",
            hostname=hostname,
            enabled=bool(enabled),
        )
    except ChesterAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ChesterAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to set static lease for {mac_norm}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    if result.get("success"):
        device_repo.set_static_ip_reservation(
            mac_address=mac_norm,
            enabled=bool(enabled),
            reserved_ip=reserved_ip if enabled else None,
        )

    return {
        "success": bool(result.get("success")),
        "mac_address": mac_norm,
        "reserved_ip": reserved_ip if enabled and result.get("success") else None,
        "enabled": bool(enabled),
        "method": result.get("method"),
        "error_code": result.get("error_code", -1),
        "detail": result.get("detail", ""),
    }
