"""
Alarm.com API Routes for HomeSentinel
# 2026-03-10: Endpoints for Alarm.com security system — partitions, sensors, locks, etc.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import json
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alarm-com", tags=["alarm-com"])

# Global references (injected from main.py)
alarm_com_client = None
db = None


class AlarmComCredentials(BaseModel):
    username: str
    password: str
    two_factor_cookie: Optional[str] = ""


class OtpRequest(BaseModel):
    method: str = "app"  # "app", "email", "sms"


class OtpSubmit(BaseModel):
    code: str
    method: str = "app"  # "app", "email", "sms"


class PartitionCommand(BaseModel):
    command: str  # arm_away, arm_stay, disarm


class LockCommand(BaseModel):
    command: str  # lock, unlock


def set_alarm_com_client(client):
    global alarm_com_client
    alarm_com_client = client


def set_db(database):
    global db
    db = database


# 2026-03-12: Extracted _get_setting/_set_setting to utils.py for reuse
from utils import get_setting as _get_setting_impl, set_setting as _set_setting_impl


def _get_setting(key: str) -> Optional[str]:
    """Get a setting value from the database (delegates to shared utils)."""
    if db is None:
        return None
    try:
        with db.get_connection() as conn:
            return _get_setting_impl(conn, key)
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {e}")
        return None


def _set_setting(key: str, value: str):
    """Set a setting value in the database (delegates to shared utils)."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    try:
        with db.get_connection() as conn:
            _set_setting_impl(conn, key, value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save setting: {e}")


def load_alarm_com_credentials_on_startup():
    """Load Alarm.com credentials — env vars take priority over DB.
    # 2026-03-10: Prefer ALARM_COM_USERNAME, ALARM_COM_PASSWORD, ALARM_COM_2FA_COOKIE env vars.
    """
    if alarm_com_client is None:
        return

    env_user = os.getenv("ALARM_COM_USERNAME", "")
    env_pass = os.getenv("ALARM_COM_PASSWORD", "")
    env_2fa = os.getenv("ALARM_COM_2FA_COOKIE", "")

    if env_user and env_pass:
        alarm_com_client.username = env_user
        alarm_com_client.password = env_pass
        if env_2fa:
            alarm_com_client.two_factor_cookie = env_2fa
        logger.info("Loaded Alarm.com credentials from environment")
        return

    # Fall back to DB
    if db is None:
        return
    creds_json = _get_setting("alarm_com_credentials")
    if not creds_json:
        return

    try:
        creds = json.loads(creds_json)
        alarm_com_client.username = creds.get("username", "")
        alarm_com_client.password = creds.get("password", "")
        alarm_com_client.two_factor_cookie = creds.get("two_factor_cookie", "")
        logger.info("Loaded Alarm.com credentials from database")
    except Exception as e:
        logger.warning(f"Failed to load Alarm.com credentials: {e}")


# --- Credential endpoints ---

@router.post("/credentials")
async def save_alarm_com_credentials(creds: AlarmComCredentials) -> Dict[str, Any]:
    """Save Alarm.com credentials and update the client."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")

    creds_data = {
        "username": creds.username,
        "password": creds.password,
        "two_factor_cookie": creds.two_factor_cookie or "",
    }
    _set_setting("alarm_com_credentials", json.dumps(creds_data))

    alarm_com_client.set_credentials(
        username=creds.username,
        password=creds.password,
        two_factor_cookie=creds.two_factor_cookie or "",
    )

    return {"success": True, "message": "Alarm.com credentials saved"}


@router.get("/status")
async def get_alarm_com_status() -> Dict[str, Any]:
    """Get Alarm.com connection status (without exposing credentials)."""
    if alarm_com_client is None:
        return {"configured": False, "logged_in": False, "username": None}

    has_credentials = bool(alarm_com_client.username and alarm_com_client.password)
    return {
        "configured": has_credentials,
        "logged_in": alarm_com_client.is_logged_in,
        "username": alarm_com_client.username if has_credentials else None,
        "has_2fa_cookie": bool(alarm_com_client.two_factor_cookie),
    }


@router.post("/login")
async def login_alarm_com() -> Dict[str, Any]:
    """Login to Alarm.com. May return otp_required if 2FA is needed."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")

    try:
        result = await alarm_com_client.login()
        return result
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/otp/request")
async def request_otp(body: OtpRequest) -> Dict[str, Any]:
    """Request OTP code via app, email, or sms."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        return await alarm_com_client.request_otp(body.method)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/otp/submit")
async def submit_otp(body: OtpSubmit) -> Dict[str, Any]:
    """Submit OTP code. Returns 2FA cookie on success (save for future logins)."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        result = await alarm_com_client.submit_otp(body.code, body.method)
        # Persist the 2FA cookie so future restarts don't need OTP again
        if result.get("two_factor_cookie"):
            existing = _get_setting("alarm_com_credentials")
            if existing:
                creds = json.loads(existing)
                creds["two_factor_cookie"] = result["two_factor_cookie"]
                _set_setting("alarm_com_credentials", json.dumps(creds))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Device endpoints ---

@router.get("/devices")
async def get_all_devices() -> Dict[str, Any]:
    """Get all Alarm.com devices grouped by category."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        devices = await alarm_com_client.get_all_devices()
        total = sum(len(v) for v in devices.values())
        return {"devices": devices, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/partitions")
async def get_partitions() -> Dict[str, Any]:
    """Get alarm partitions with arm/disarm state."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        partitions = await alarm_com_client.get_partitions()
        return {"partitions": partitions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/partitions/{partition_id}/command")
async def send_partition_command(partition_id: str, body: PartitionCommand) -> Dict[str, Any]:
    """Arm/disarm a partition."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")

    cmd_map = {
        "arm_away": alarm_com_client.arm_away,
        "arm_stay": alarm_com_client.arm_stay,
        "disarm": alarm_com_client.disarm,
    }
    handler = cmd_map.get(body.command)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unknown command: {body.command}")

    try:
        result = await handler(partition_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensors")
async def get_sensors() -> Dict[str, Any]:
    """Get all sensors."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        sensors = await alarm_com_client.get_sensors()
        return {"sensors": sensors, "total": len(sensors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locks")
async def get_locks() -> Dict[str, Any]:
    """Get smart locks."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        locks = await alarm_com_client.get_locks()
        return {"locks": locks, "total": len(locks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/locks/{lock_id}/command")
async def send_lock_command(lock_id: str, body: LockCommand) -> Dict[str, Any]:
    """Lock/unlock a smart lock."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")

    cmd_map = {"lock": alarm_com_client.lock, "unlock": alarm_com_client.unlock}
    handler = cmd_map.get(body.command)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unknown command: {body.command}")

    try:
        result = await handler(lock_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lights")
async def get_lights() -> Dict[str, Any]:
    """Get Alarm.com-connected lights."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        lights = await alarm_com_client.get_lights()
        return {"lights": lights, "total": len(lights)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thermostats")
async def get_thermostats() -> Dict[str, Any]:
    """Get thermostats."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        thermostats = await alarm_com_client.get_thermostats()
        return {"thermostats": thermostats, "total": len(thermostats)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cameras")
async def get_cameras() -> Dict[str, Any]:
    """Get cameras."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        cameras = await alarm_com_client.get_cameras()
        return {"cameras": cameras, "total": len(cameras)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/garage-doors")
async def get_garage_doors() -> Dict[str, Any]:
    """Get garage doors."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        doors = await alarm_com_client.get_garage_doors()
        return {"garage_doors": doors, "total": len(doors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/water-sensors")
async def get_water_sensors() -> Dict[str, Any]:
    """Get water/flood sensors."""
    if alarm_com_client is None:
        raise HTTPException(status_code=500, detail="Alarm.com client not initialized")
    try:
        sensors = await alarm_com_client.get_water_sensors()
        return {"water_sensors": sensors, "total": len(sensors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
