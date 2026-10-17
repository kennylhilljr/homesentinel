"""API routes for local service observability."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/local-services", tags=["local-services"])
local_service_monitor = None


def set_local_service_monitor(service: Any) -> None:
    global local_service_monitor
    local_service_monitor = service


def _service():
    if local_service_monitor is None:
        raise HTTPException(status_code=503, detail="Local service monitor not initialized")
    return local_service_monitor


@router.get("")
async def list_local_services():
    return await asyncio.to_thread(_service().snapshot)


@router.get("/events")
async def list_local_service_events(limit: int = Query(100, ge=1, le=1000)):
    return {"events": await asyncio.to_thread(_service().get_events, limit)}


@router.get("/traffic")
async def list_local_service_traffic(limit: int = Query(300, ge=1, le=5000)):
    return {"samples": await asyncio.to_thread(_service().get_traffic, limit)}


async def _control(service_id: str, action: str):
    try:
        return await asyncio.to_thread(_service().control, service_id, action)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Service is not allowlisted") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{service_id}/restart")
async def restart_local_service(service_id: str):
    return await _control(service_id, "restart")


@router.post("/{service_id}/stop")
async def stop_local_service(service_id: str):
    return await _control(service_id, "stop")

