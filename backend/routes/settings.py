"""
Settings API Routes
Endpoints for managing Deco/Alexa/Chester credentials
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Global references (injected from main.py)
db = None
deco_client = None
chester_client = None


class DecoCredentials(BaseModel):
    username: str
    password: str
    mode: str = "cloud"  # "cloud" or "local"
    local_endpoint: Optional[str] = None


class ChesterCredentials(BaseModel):
    host: str = "192.168.12.1"
    port: int = 80
    username: str = "admin"
    password: str
    use_https: bool = False
    verify_ssl: bool = False


def set_db(database):
    global db
    db = database


def set_deco_client(client):
    global deco_client
    deco_client = client


def set_chester_client(client):
    global chester_client
    chester_client = client


def _get_setting(key: str) -> Optional[str]:
    """Get a setting value from the database"""
    if db is None:
        return None
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {e}")
        return None


def _set_setting(key: str, value: str):
    """Set a setting value in the database"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
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
        raise HTTPException(status_code=500, detail=f"Failed to save setting: {e}")


def load_deco_credentials_on_startup():
    """Load saved Deco credentials into the DecoClient on startup"""
    if deco_client is None or db is None:
        return

    creds_json = _get_setting("deco_credentials")
    if not creds_json:
        return

    try:
        creds = json.loads(creds_json)
        deco_client.username = creds.get("username", "")
        deco_client.password = creds.get("password", "")

        mode = creds.get("mode", "cloud")
        if mode == "local":
            local_ep = creds.get("local_endpoint", deco_client.DEFAULT_LOCAL_ENDPOINT)
            deco_client.use_cloud = False
            deco_client.active_endpoint = local_ep
            deco_client.local_endpoint = local_ep
            deco_client.verify_ssl = False
        else:
            deco_client.use_cloud = True
            deco_client.active_endpoint = deco_client.cloud_endpoint
            deco_client.verify_ssl = True

        logger.info(f"Loaded Deco credentials from database (mode: {mode})")
    except Exception as e:
        logger.warning(f"Failed to load Deco credentials: {e}")


def load_chester_credentials_on_startup():
    """Load saved Chester credentials into the ChesterClient on startup"""
    if chester_client is None or db is None:
        return

    creds_json = _get_setting("chester_credentials")
    if not creds_json:
        return

    try:
        creds = json.loads(creds_json)
        chester_client.set_credentials(
            host=creds.get("host", "192.168.12.1"),
            username=creds.get("username", "admin"),
            password=creds.get("password", ""),
            port=int(creds.get("port", 80)),
            use_https=bool(creds.get("use_https", False)),
            verify_ssl=bool(creds.get("verify_ssl", False)),
        )
        logger.info("Loaded Chester credentials from database")
    except Exception as e:
        logger.warning(f"Failed to load Chester credentials: {e}")


@router.post("/deco/credentials")
async def save_deco_credentials(creds: DecoCredentials) -> Dict[str, Any]:
    """Save Deco credentials and update the client"""
    if deco_client is None:
        raise HTTPException(status_code=500, detail="Deco client not initialized")

    # Save to database
    creds_data = {
        "username": creds.username,
        "password": creds.password,
        "mode": creds.mode,
        "local_endpoint": creds.local_endpoint,
    }
    _set_setting("deco_credentials", json.dumps(creds_data))

    # Update the client
    deco_client.username = creds.username
    deco_client.password = creds.password

    if creds.mode == "local":
        local_ep = creds.local_endpoint or deco_client.DEFAULT_LOCAL_ENDPOINT
        deco_client.use_cloud = False
        deco_client.active_endpoint = local_ep
        deco_client.local_endpoint = local_ep
        deco_client.verify_ssl = False
    else:
        deco_client.use_cloud = True
        deco_client.active_endpoint = deco_client.cloud_endpoint
        deco_client.verify_ssl = True

    # Clear any existing session
    deco_client._session_token = None
    deco_client._token_expiry = None

    return {
        "success": True,
        "message": "Deco credentials saved",
        "mode": creds.mode,
        "endpoint": deco_client.active_endpoint,
    }


@router.get("/deco/status")
async def get_deco_status() -> Dict[str, Any]:
    """Get Deco connection status (without exposing credentials)"""
    if deco_client is None:
        return {
            "configured": False,
            "authenticated": False,
            "mode": None,
            "endpoint": None,
        }

    has_credentials = bool(deco_client.username and deco_client.password)
    return {
        "configured": has_credentials,
        "authenticated": deco_client.is_authenticated(),
        "mode": "cloud" if deco_client.use_cloud else "local",
        "endpoint": deco_client.active_endpoint,
        "username": deco_client.username if has_credentials else None,
    }


@router.post("/deco/test")
async def test_deco_connection(creds: DecoCredentials) -> Dict[str, Any]:
    """Test Deco connection with provided credentials"""
    from services.deco_client import DecoClient, InvalidCredentialsError, APIConnectionError

    try:
        test_client = DecoClient(
            use_cloud=(creds.mode == "cloud"),
            local_endpoint=creds.local_endpoint or DecoClient.DEFAULT_LOCAL_ENDPOINT,
            verify_ssl=(creds.mode == "cloud"),
        )
        test_client.authenticate(creds.username, creds.password)
        test_client.close()

        return {
            "success": True,
            "message": "Connection successful",
            "mode": creds.mode,
        }
    except InvalidCredentialsError as e:
        return {
            "success": False,
            "message": f"Authentication failed: {e}",
            "mode": creds.mode,
        }
    except APIConnectionError as e:
        return {
            "success": False,
            "message": f"Connection failed: {e}",
            "mode": creds.mode,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {e}",
            "mode": creds.mode,
        }


@router.post("/chester/credentials")
async def save_chester_credentials(creds: ChesterCredentials) -> Dict[str, Any]:
    """Save Chester router credentials and update client config"""
    if chester_client is None:
        raise HTTPException(status_code=500, detail="Chester client not initialized")

    creds_data = {
        "host": creds.host,
        "port": creds.port,
        "username": creds.username,
        "password": creds.password,
        "use_https": creds.use_https,
        "verify_ssl": creds.verify_ssl,
    }
    _set_setting("chester_credentials", json.dumps(creds_data))

    chester_client.set_credentials(
        host=creds.host,
        username=creds.username,
        password=creds.password,
        port=creds.port,
        use_https=creds.use_https,
        verify_ssl=creds.verify_ssl,
    )

    return {
        "success": True,
        "message": "Chester credentials saved",
        "endpoint": chester_client.base_url,
    }


@router.get("/chester/status")
async def get_chester_status() -> Dict[str, Any]:
    """Get Chester connection status (without exposing password)"""
    if chester_client is None:
        return {
            "configured": False,
            "authenticated": False,
            "host": None,
            "endpoint": None,
        }

    has_credentials = bool(chester_client.username and chester_client.password)
    return {
        "configured": has_credentials,
        "authenticated": not chester_client._needs_login() if has_credentials else False,
        "host": chester_client.host,
        "endpoint": chester_client.base_url,
        "username": chester_client.username if has_credentials else None,
        "use_https": chester_client.use_https,
    }


@router.post("/chester/test")
async def test_chester_connection(creds: ChesterCredentials) -> Dict[str, Any]:
    """Test Chester/OpenWrt connection with provided credentials"""
    from services.chester_client import ChesterClient

    test_client = ChesterClient(
        host=creds.host,
        username=creds.username,
        password=creds.password,
        port=creds.port,
        use_https=creds.use_https,
        verify_ssl=creds.verify_ssl,
    )
    try:
        result = test_client.test_connection()
        board = result.get("board", {})
        return {
            "success": True,
            "message": "Connection successful",
            "board_model": board.get("model"),
            "board_release": board.get("release"),
            "endpoint": test_client.base_url,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {e}",
            "endpoint": test_client.base_url,
        }
    finally:
        test_client.close()
