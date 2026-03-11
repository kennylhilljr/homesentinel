"""
Chester 5G Router API routes.

2026-03-11: Added /system-info endpoint for full cellular signal data.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from services.chester_client import ChesterAPIError, ChesterAuthError

router = APIRouter(prefix="/api/chester", tags=["chester"])

chester_client = None
chester_service = None


def set_chester_client(client):
    global chester_client
    chester_client = client


def set_chester_service(service):
    global chester_service
    chester_service = service


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
