#!/usr/bin/env python3
"""
HomeSentinel Backend - FastAPI Application
Main entry point for the backend server
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

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
    return {
        "status": "healthy",
        "service": "HomeSentinel Backend"
    }

@app.get("/api/devices")
async def get_devices():
    """Get list of discovered devices"""
    return {
        "devices": [],
        "total": 0
    }

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
