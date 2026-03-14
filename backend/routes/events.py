"""
Event and Alert API Routes
Endpoints for retrieving and managing device events and alerts
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create router for event endpoints
router = APIRouter(prefix="/api/events", tags=["events"])

# Global service instances (injected from main.py)
event_service = None
device_repo = None


def set_event_service(service):
    """Set the event service (called from main.py)"""
    global event_service
    event_service = service


def set_device_repo(repo):
    """Set the device repository (called from main.py)"""
    global device_repo
    device_repo = repo


# Request/Response models
class EventResponse(BaseModel):
    event_id: str
    device_id: str
    device_name: Optional[str] = None
    device_mac: Optional[str] = None
    event_type: str
    timestamp: str
    description: Optional[str] = None
    metadata: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    alert_id: str
    device_id: str
    device_name: Optional[str] = None
    device_mac: Optional[str] = None
    event_id: str
    alert_type: str
    dismissed: bool
    dismissed_at: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    events: List[EventResponse]
    total: int
    limit: int
    offset: int


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    limit: int
    offset: int


class AlertDismissRequest(BaseModel):
    reason: Optional[str] = None


# Helper function to enrich events with device info
def _enrich_event(event: dict) -> dict:
    """Add device name and MAC to event response"""
    if device_repo and event.get('device_id'):
        try:
            device = device_repo.get_by_id(event['device_id'])
            if device:
                event['device_name'] = device.get('friendly_name') or device.get('mac_address') or event['device_id']
                event['device_mac'] = device.get('mac_address')
        except Exception as e:
            logger.warning(f"Failed to enrich event with device info: {e}")
    return event


def _enrich_alert(alert: dict) -> dict:
    """Add device name and MAC to alert response"""
    if device_repo and alert.get('device_id'):
        try:
            device = device_repo.get_by_id(alert['device_id'])
            if device:
                alert['device_name'] = device.get('friendly_name') or device.get('mac_address') or alert['device_id']
                alert['device_mac'] = device.get('mac_address')
        except Exception as e:
            logger.warning(f"Failed to enrich alert with device info: {e}")
    return alert


# ─────────────────────────────────────────────────────────────────────────────
# Event Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=EventListResponse)
async def get_events(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type (connected, disconnected, online, offline, new_device)"),
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip")
):
    """
    Retrieve device events with optional filtering.

    Query Parameters:
    - device_id: Filter by device UUID
    - event_type: Filter by event type (connected, disconnected, online, offline, new_device)
    - start_date: Filter events from this date (ISO 8601 format)
    - end_date: Filter events until this date (ISO 8601 format)
    - limit: Maximum number of events to return (default: 100, max: 1000)
    - offset: Number of events to skip for pagination (default: 0)

    Returns:
    - List of events with device name and MAC address enrichment
    - Total count of matching events
    """
    if not event_service:
        raise HTTPException(status_code=503, detail="Event service not initialized")

    try:
        # Get events using event service
        events = event_service.get_events(
            device_id=device_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        # Enrich events with device information
        enriched_events = [_enrich_event(event) for event in events]

        # Get total count
        total = event_service.get_event_count(
            device_id=device_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date
        )

        return EventListResponse(
            events=enriched_events,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error retrieving events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve events: {str(e)}")


@router.get("/{device_id}", response_model=EventListResponse)
async def get_device_events(
    device_id: str,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve events for a specific device.

    Parameters:
    - device_id: UUID of the device
    - event_type: Optional filter by event type
    - start_date: Optional filter events from this date
    - end_date: Optional filter events until this date
    - limit: Maximum number of events to return
    - offset: Number of events to skip for pagination

    Returns:
    - List of events for the device with enriched device information
    """
    if not event_service:
        raise HTTPException(status_code=503, detail="Event service not initialized")

    try:
        # Verify device exists
        if device_repo:
            device = device_repo.get_by_id(device_id)
            if not device:
                raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        # Get events
        events = event_service.get_events(
            device_id=device_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        # Enrich events
        enriched_events = [_enrich_event(event) for event in events]

        # Get total count
        total = event_service.get_event_count(
            device_id=device_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date
        )

        return EventListResponse(
            events=enriched_events,
            total=total,
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving events for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve events: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Alert Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type (new_device, device_reconnected, device_offline)"),
    dismissed: Optional[bool] = Query(False, description="Filter by dismissed status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve device alerts with optional filtering.

    Query Parameters:
    - device_id: Filter by device UUID
    - alert_type: Filter by alert type (new_device, device_reconnected, device_offline)
    - dismissed: Filter by dismissed status (default: False = show active alerts only)
    - limit: Maximum number of alerts to return (default: 50, max: 500)
    - offset: Number of alerts to skip for pagination

    Returns:
    - List of alerts with device information
    - Total count of matching alerts
    """
    if not event_service:
        raise HTTPException(status_code=503, detail="Event service not initialized")

    try:
        # Get alerts using event service
        alerts = event_service.get_alerts(
            dismissed=dismissed,
            device_id=device_id,
            limit=limit,
            offset=offset
        )

        # Filter by alert_type if specified
        if alert_type:
            alerts = [a for a in alerts if a.get('alert_type') == alert_type]

        # Enrich alerts with device information
        enriched_alerts = [_enrich_alert(alert) for alert in alerts]

        # Get total count (note: simplified, doesn't count by alert_type)
        total = len(enriched_alerts)

        return AlertListResponse(
            alerts=enriched_alerts,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")


@router.get("/alerts/{device_id}", response_model=AlertListResponse)
async def get_device_alerts(
    device_id: str,
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    dismissed: Optional[bool] = Query(False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve alerts for a specific device.

    Parameters:
    - device_id: UUID of the device
    - alert_type: Optional filter by alert type
    - dismissed: Filter by dismissed status (default: False)
    - limit: Maximum number of alerts to return
    - offset: Number of alerts to skip for pagination

    Returns:
    - List of alerts for the device with enriched device information
    """
    if not event_service:
        raise HTTPException(status_code=503, detail="Event service not initialized")

    try:
        # Verify device exists
        if device_repo:
            device = device_repo.get_by_id(device_id)
            if not device:
                raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        # Get alerts
        alerts = event_service.get_alerts(
            dismissed=dismissed,
            device_id=device_id,
            limit=limit,
            offset=offset
        )

        # Filter by alert_type if specified
        if alert_type:
            alerts = [a for a in alerts if a.get('alert_type') == alert_type]

        # Enrich alerts
        enriched_alerts = [_enrich_alert(alert) for alert in alerts]

        return AlertListResponse(
            alerts=enriched_alerts,
            total=len(enriched_alerts),
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alerts for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")


@router.post("/alerts/{alert_id}/dismiss", response_model=Dict[str, Any])
async def dismiss_alert(
    alert_id: str,
    request: AlertDismissRequest = None
):
    """
    Dismiss an alert (mark as dismissed).

    Parameters:
    - alert_id: UUID of the alert to dismiss
    - reason: Optional reason for dismissal

    Returns:
    - Updated alert object
    """
    if not event_service:
        raise HTTPException(status_code=503, detail="Event service not initialized")

    try:
        # Dismiss alert
        success = event_service.dismiss_alert(alert_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        # Return updated alert
        alert = event_service.get_alerts(limit=1, offset=0)
        alert_found = next((a for a in alert if a.get('alert_id') == alert_id), None)

        if not alert_found:
            return {"alert_id": alert_id, "dismissed": True, "dismissed_at": datetime.now(timezone.utc).isoformat()}

        return _enrich_alert(alert_found)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to dismiss alert: {str(e)}")


@router.get("/stats", response_model=Dict[str, Any])
async def get_event_stats():
    """
    Retrieve event statistics.

    Returns:
    - Total number of events
    - Events grouped by type
    - Number of active alerts
    - Number of events in the last 24 hours
    """
    if not event_service:
        raise HTTPException(status_code=503, detail="Event service not initialized")

    try:
        stats = event_service.get_event_stats()
        return stats

    except Exception as e:
        logger.error(f"Error retrieving event stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")
