"""
Server-Sent Events (SSE) endpoint for real-time device status updates.
2026-03-12: Replaces 5-second polling with push-based updates.
"""
import asyncio
import json
import logging
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sse", tags=["SSE"])

# 2026-03-12: Simple pub/sub — polling service publishes, SSE clients subscribe
_subscribers: list = []  # list of asyncio.Queue


def publish_event(event_type: str, data: dict):
    """Publish an event to all SSE subscribers. Called from polling/scan services."""
    message = {"type": event_type, "data": data, "timestamp": time.time()}
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(q)
    # 2026-03-12: Remove dead/full queues to prevent memory leaks
    for q in dead:
        _subscribers.remove(q)


async def _event_generator(queue: asyncio.Queue):
    """Generate SSE events from a subscriber queue."""
    try:
        # Send initial keepalive
        yield f"event: connected\ndata: {json.dumps({'status': 'ok'})}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"event: {msg['type']}\ndata: {json.dumps(msg['data'])}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive every 30s to prevent connection timeout
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)


@router.get("/events")
async def sse_events():
    """SSE stream of device status changes, scan results, alerts, etc."""
    queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)
    return StreamingResponse(
        _event_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
