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
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database and services
from db import Database, NetworkDeviceRepository, PollingConfigRepository
from services import NetworkDeviceService
from services.polling_service import PollingServiceManager

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

# Global database and service instances
db = None
device_service = None
polling_manager = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    global db, device_service, polling_manager

    logger.info("Starting HomeSentinel Backend...")

    # Initialize database
    db = Database()
    db.run_migrations()
    logger.info("Database initialized and migrations applied")

    # Initialize device service
    device_service = NetworkDeviceService(db)
    logger.info("Device service initialized")

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
    global db, polling_manager

    logger.info("Shutting down HomeSentinel Backend...")

    # Stop polling
    if polling_manager:
        await polling_manager.stop()
        logger.info("Polling service stopped")

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
