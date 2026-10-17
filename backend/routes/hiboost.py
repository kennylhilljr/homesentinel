"""
HiBoost Signal Booster API routes.

Provides endpoints for monitoring and controlling the HiBoost 10K signal booster
via the Signal Supervisor cloud API.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.hiboost_client import HiBoostAPIError, HiBoostAuthError

router = APIRouter(prefix="/api/hiboost", tags=["hiboost"])

hiboost_client = None
hiboost_service = None
_db = None


def set_db(database):
    global _db
    _db = database


def set_hiboost_client(client):
    global hiboost_client
    hiboost_client = client


def set_hiboost_service(service):
    global hiboost_service
    hiboost_service = service


class MGCUpdate(BaseModel):
    band: str
    mgc_ul: Optional[int] = None
    mgc_dl: Optional[int] = None


class RFSwitchUpdate(BaseModel):
    band: str
    enabled: bool


@router.get("/status")
async def get_hiboost_status() -> Dict[str, Any]:
    """Get HiBoost connection status and device overview."""
    if hiboost_service is None:
        return {"connected": False, "error": "HiBoost service not initialized"}
    try:
        dashboard = hiboost_service.get_dashboard()
        devices = dashboard.get("devices", [])
        return {
            "connected": True,
            "online_total": dashboard.get("onlineTotal", 0),
            "offline_total": dashboard.get("offlineTotal", 0),
            "alarm_total": dashboard.get("alarmTotal", 0),
            "devices": devices,
        }
    except HiBoostAuthError as e:
        return {"connected": False, "error": f"Auth failed: {e}"}
    except HiBoostAPIError as e:
        return {"connected": False, "error": str(e)}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/devices")
async def get_hiboost_devices() -> Dict[str, Any]:
    """List all registered HiBoost devices."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        devices = hiboost_service.get_device_list()
        return {"devices": devices, "total": len(devices)}
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/devices/{device_id}")
async def get_hiboost_device_detail(device_id: str) -> Dict[str, Any]:
    """Get full device detail with parsed RF parameters."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        return hiboost_service.get_device_detail(device_id)
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/devices/{device_id}/rf-params")
async def get_hiboost_rf_params(device_id: str) -> Dict[str, Any]:
    """Get all RF parameters for all bands."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        return hiboost_service.get_rf_params(device_id)
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/devices/{device_id}/bands/{band_name}")
async def get_hiboost_band(device_id: str, band_name: str) -> Dict[str, Any]:
    """Get RF parameters for a specific band."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        band = hiboost_service.get_band_params(device_id, band_name)
        if band is None:
            raise HTTPException(status_code=404, detail=f"Band {band_name} not found")
        return band
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/devices/{device_id}/mgc")
async def update_hiboost_mgc(device_id: str, update: MGCUpdate) -> Dict[str, Any]:
    """Update MGC (Manual Gain Control) for a band. Values 0-20 dB."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        return hiboost_service.update_mgc(
            device_id, update.band, mgc_ul=update.mgc_ul, mgc_dl=update.mgc_dl
        )
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/devices/{device_id}/rf-switch")
async def update_hiboost_rf_switch(device_id: str, update: RFSwitchUpdate) -> Dict[str, Any]:
    """Toggle RF switch for a band on/off."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        return hiboost_service.update_rf_switch(device_id, update.band, update.enabled)
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/devices/{device_id}/refresh")
async def refresh_hiboost_device(device_id: str) -> Dict[str, Any]:
    """Force refresh device data (clear cache)."""
    if hiboost_service is None:
        raise HTTPException(status_code=500, detail="HiBoost service not initialized")
    try:
        hiboost_service.clear_cache()
        return hiboost_service.get_rf_params(device_id)
    except HiBoostAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except HiBoostAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/history")
async def get_hiboost_history(hours: int = Query(default=24, ge=1)) -> Dict[str, Any]:
    """Get historical RF data for charting. Returns time-series per band."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with _db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT band, output_power_dl, gain_dl, gain_ul, mgc_dl, mgc_ul,
                      temperature, timestamp
               FROM hiboost_history
               WHERE timestamp >= ?
               ORDER BY timestamp ASC""",
            (cutoff,),
        )
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]

    # Group by timestamp for charting
    by_time: Dict[str, Dict] = {}
    for row in rows:
        r = dict(zip(cols, row))
        ts = r["timestamp"]
        if ts not in by_time:
            by_time[ts] = {"timestamp": ts, "temperature": r.get("temperature")}
        band = r["band"]
        by_time[ts][f"{band}_power"] = r["output_power_dl"]
        by_time[ts][f"{band}_gain"] = r["gain_dl"]

    data = list(by_time.values())

    # Format timestamps for display
    for d in data:
        try:
            dt = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
            d["time"] = dt.strftime("%-m/%-d %H:%M")
            d["dateTime"] = dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            d["time"] = d["timestamp"]
            d["dateTime"] = d["timestamp"]

    return {
        "data": data,
        "total": len(data),
        "hours": hours,
        "bands": ["LTE700", "CELL800", "PCS1900", "AWS2100"],
    }
