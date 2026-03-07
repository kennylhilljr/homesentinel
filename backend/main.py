#!/usr/bin/env python3
"""
HomeSentinel Backend - FastAPI Application
Main entry point for the backend server
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging
from datetime import datetime
from typing import Optional
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database and services
from db import Database, NetworkDeviceRepository, PollingConfigRepository, DeviceGroupRepository, DeviceGroupMemberRepository
from services import NetworkDeviceService, DeviceSearchService
from services.polling_service import PollingServiceManager
from services.oui_service import OUIService
from services.deco_service import DecoService
from services.deco_client import DecoClient
from routes import deco as deco_routes
import uuid
from pydantic import BaseModel

app = FastAPI(
    title="HomeSentinel API",
    description="Home Network Monitor & Device Management Platform",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Deco routes
app.include_router(deco_routes.router)

# Pydantic models
class DeviceUpdate(BaseModel):
    friendly_name: str = None
    device_type: str = None
    notes: str = None


class DeviceGroupCreate(BaseModel):
    name: str
    color: str = '#3498db'


class DeviceGroupUpdate(BaseModel):
    name: str = None
    color: str = None


class DeviceGroupMemberAdd(BaseModel):
    device_id: str


# Global database and service instances
db = None
device_service = None
search_service = None
polling_manager = None
group_repo = None
member_repo = None
oui_service = None
deco_service = None
deco_client = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    global db, device_service, search_service, polling_manager, group_repo, member_repo, oui_service, deco_service, deco_client

    logger.info("Starting HomeSentinel Backend...")

    # Initialize database
    db = Database()
    db.run_migrations()
    logger.info("Database initialized and migrations applied")

    # Initialize OUI service
    oui_service = OUIService()
    logger.info(f"OUI service initialized with {oui_service.get_database_size()} entries")

    # Initialize device service
    device_service = NetworkDeviceService(db)
    logger.info("Device service initialized")

    # Initialize search service
    search_service = DeviceSearchService(db)
    logger.info("Search service initialized")

    # Initialize group repositories
    group_repo = DeviceGroupRepository(db)
    member_repo = DeviceGroupMemberRepository(db)
    logger.info("Device group repositories initialized")

    # Initialize Deco client and service
    try:
        deco_client = DecoClient()
        deco_service = DecoService(deco_client=deco_client)
        deco_routes.set_deco_service(deco_service)
        logger.info("Deco service initialized and routes configured")
    except Exception as e:
        logger.warning(f"Failed to initialize Deco service: {e}")

    # Initialize polling service
    polling_manager = PollingServiceManager()
    polling_interval = int(os.getenv("POLLING_INTERVAL_SECONDS", "60"))
    subnet = os.getenv("NETWORK_SUBNET", "192.168.1.0/24")
    polling_manager.initialize(device_service, polling_interval, subnet)
    logger.info(f"Polling service initialized (interval: {polling_interval}s, subnet: {subnet})")

    # Start background polling
    try:
        await polling_manager.start()
        logger.info("Background polling started")
    except Exception as e:
        logger.error(f"Failed to start polling: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global db, polling_manager, deco_client

    logger.info("Shutting down HomeSentinel Backend...")

    # Stop polling
    if polling_manager:
        await polling_manager.stop()
        logger.info("Polling service stopped")

    # Close Deco client
    if deco_client:
        deco_client.close()
        logger.info("Deco client closed")

    # Close database
    if db:
        db.close()
        logger.info("Database closed")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "HomeSentinel API is running",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    global db
    db_status = "connected" if db else "disconnected"
    return {
        "status": "healthy",
        "service": "HomeSentinel Backend",
        "database": db_status
    }


@app.get("/api/devices")
async def get_devices():
    """Get list of discovered devices"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    devices = device_service.list_devices()
    return {
        "devices": devices,
        "total": len(devices),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/devices/online")
async def get_online_devices():
    """Get list of online devices"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    devices = device_service.list_online_devices()
    return {
        "devices": devices,
        "total": len(devices),
        "status_filter": "online"
    }


@app.get("/api/devices/offline")
async def get_offline_devices():
    """Get list of offline devices"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    devices = device_service.list_offline_devices()
    return {
        "devices": devices,
        "total": len(devices),
        "status_filter": "offline"
    }


@app.get("/api/devices/search")
async def search_devices(q: str = "", status: Optional[str] = None):
    """
    Search for devices across multiple fields.

    Query string 'q' searches:
    - MAC address (prefix match)
    - IP address (substring match)
    - Hostname (contains match)
    - Friendly name (contains match)
    - Vendor name (contains match)

    Optional 'status' filter: 'online' or 'offline'

    Returns devices matching the query, sorted by last_seen.
    """
    global search_service
    if search_service is None:
        raise HTTPException(status_code=500, detail="Search service not initialized")

    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required and cannot be empty")

    try:
        devices = search_service.search(q, status)
        return {
            "query": q,
            "status_filter": status,
            "devices": devices,
            "total": len(devices),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/polling")
async def get_polling_config():
    """Get polling configuration"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    config = device_service.get_polling_config()
    status = polling_manager.get_status()

    return {
        "interval": config.get('polling_interval_seconds', 60),
        "last_scan": config.get('last_scan_timestamp'),
        "polling_status": status
    }


@app.post("/api/config/polling")
async def update_polling_config(interval: int):
    """Update polling interval"""
    global device_service, polling_manager
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    try:
        config = device_service.set_polling_interval(interval)
        polling_manager.set_interval(interval)
        return {
            "success": True,
            "interval": config.get('polling_interval_seconds'),
            "message": f"Polling interval updated to {interval} seconds"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/devices/scan-now")
async def trigger_manual_scan():
    """Manually trigger a network scan"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    try:
        subnet = os.getenv("NETWORK_SUBNET", "192.168.1.0/24")
        result = device_service.scan_and_update(subnet)
        return {
            "success": True,
            "devices_found": result.get('devices_found', 0),
            "devices_added": result.get('devices_added', 0),
            "devices_updated": result.get('devices_updated', 0),
            "devices_offline": result.get('devices_offline', 0),
            "timestamp": result.get('timestamp'),
            "scan_time_seconds": result.get('scan_time_seconds', 0)
        }
    except Exception as e:
        logger.error(f"Manual scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Device metadata endpoints
@app.get("/api/devices/{device_id}")
async def get_device_details(device_id: str):
    """Get full device details including vendor information"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    device = device_service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device


@app.put("/api/devices/{device_id}")
async def update_device(device_id: str, updates: DeviceUpdate):
    """Update device metadata"""
    global device_service
    if device_service is None:
        raise HTTPException(status_code=500, detail="Device service not initialized")

    try:
        device = device_service.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if updates.friendly_name:
            device_service.update_device_friendly_name(device_id, updates.friendly_name)
        if updates.device_type:
            device_service.update_device_type(device_id, updates.device_type)
        if updates.notes:
            device_service.set_device_notes(device_id, updates.notes)

        updated_device = device_service.get_device(device_id)
        return updated_device

    except Exception as e:
        logger.error(f"Failed to update device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Device Group endpoints
@app.post("/api/device-groups")
async def create_device_group(group_data: DeviceGroupCreate):
    """Create a new device group"""
    global group_repo
    if group_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        group_id = str(uuid.uuid4())
        group = group_repo.create_group(group_id, group_data.name, group_data.color)
        return group
    except Exception as e:
        logger.error(f"Failed to create group: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/device-groups")
async def list_device_groups():
    """List all device groups"""
    global group_repo
    if group_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        groups = group_repo.list_all()
        return {
            "groups": groups,
            "total": len(groups)
        }
    except Exception as e:
        logger.error(f"Failed to list groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device-groups/{group_id}")
async def get_device_group(group_id: str):
    """Get group details with members"""
    global group_repo, member_repo
    if group_repo is None or member_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        group = group_repo.get_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        members = member_repo.get_group_members(group_id)
        return {
            **group,
            "members": members,
            "member_count": len(members)
        }
    except Exception as e:
        logger.error(f"Failed to get group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/device-groups/{group_id}")
async def update_device_group(group_id: str, updates: DeviceGroupUpdate):
    """Update group metadata"""
    global group_repo
    if group_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        group = group_repo.get_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        updated_group = group_repo.update_group(group_id, updates.name, updates.color)
        return updated_group
    except Exception as e:
        logger.error(f"Failed to update group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/device-groups/{group_id}")
async def delete_device_group(group_id: str):
    """Delete a device group"""
    global group_repo
    if group_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        success = group_repo.delete_group(group_id)
        if not success:
            raise HTTPException(status_code=404, detail="Group not found")

        return {"success": True, "message": "Group deleted"}
    except Exception as e:
        logger.error(f"Failed to delete group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device-groups/{group_id}/members")
async def add_device_to_group(group_id: str, member_data: DeviceGroupMemberAdd):
    """Add device to group"""
    global group_repo, member_repo, device_service
    if group_repo is None or member_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        group = group_repo.get_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        device = device_service.get_device(member_data.device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        member_repo.add_member(group_id, member_data.device_id)
        return {"success": True, "message": "Device added to group"}
    except Exception as e:
        logger.error(f"Failed to add member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/device-groups/{group_id}/members/{device_id}")
async def remove_device_from_group(group_id: str, device_id: str):
    """Remove device from group"""
    global group_repo, member_repo
    if group_repo is None or member_repo is None:
        raise HTTPException(status_code=500, detail="Group service not initialized")

    try:
        success = member_repo.remove_member(group_id, device_id)
        if not success:
            raise HTTPException(status_code=404, detail="Membership not found")

        return {"success": True, "message": "Device removed from group"}
    except Exception as e:
        logger.error(f"Failed to remove member: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # SSL certificate setup
    cert_dir = "./backend/certs"
    cert_file = f"{cert_dir}/cert.pem"
    key_file = f"{cert_dir}/key.pem"

    # Use SSL if certificates exist
    port = int(os.getenv("BACKEND_PORT", "8443"))
    if os.path.exists(cert_file) and os.path.exists(key_file):
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file,
            log_level="info"
        )
    else:
        # Fall back to HTTP if no certificates
        print("Warning: SSL certificates not found, running on HTTP")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
