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

from middleware import auth as auth_middleware

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sse", tags=["SSE"])

# 2026-03-12: Simple pub/sub — polling service publishes, SSE clients subscribe
_subscribers: list = []  # list of asyncio.Queue


def publish_event(event_type: str, data: dict):
    """Publish an event to all SSE subscribers. Called from polling/scan services."""
    message = {
        "type": event_type,
        "timestamp": time.time(),
        "data": data if data is not None else {},
    }
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
        # Send initial keepalive with consistent schema
        yield f"event: connected\ndata: {json.dumps({'type': 'connected', 'timestamp': time.time(), 'data': {'status': 'ok'}})}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"event: {msg['type']}\ndata: {json.dumps({'type': msg['type'], 'timestamp': msg.get('timestamp', time.time()), 'data': msg.get('data', {})})}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive every 30s to prevent connection timeout
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        raise
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)


@router.get("/events")
async def sse_events():
    """SSE stream of device status changes, scan results, alerts, etc.

    With an API key configured, connect with ?token=<token from POST /api/sse/token>.
    """
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


@router.post("/token")
async def sse_token():
    """Issue a short-lived, single-use token for opening /api/sse/events.

    The auth middleware requires X-API-Key here; the token is accepted nowhere else.
    Returns token=None when auth is disabled, in which case connect without a token.
    """
    token = auth_middleware.issue_sse_token()
    return {"token": token, "expires_in": auth_middleware.SSE_TOKEN_TTL_SECONDS if token else None}
