"""
API Key Authentication Middleware for HomeSentinel
# 2026-03-12: Checks X-API-Key header on /api/* requests for optional API key auth.
"""

import hmac
import os
import logging
import secrets
import time
from hashlib import sha256

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 2026-03-12: Read API key from env var. If empty/unset, auth is disabled (backwards compat).
# Stripped like startup_policy and the dashboard prompt do, so a whitespace-only key means
# auth off everywhere and a key pasted with stray spaces still matches.
HOMESENTINEL_API_KEY = os.getenv("HOMESENTINEL_API_KEY", "").strip()

# EventSource cannot set headers, so the SSE stream authenticates with a short-lived,
# single-use token issued by the key-protected POST /api/sse/token. The long-lived API
# key never appears in a URL.
# Marks 401s from this middleware, so the dashboard can tell them apart from
# integration (Deco, Alexa, ...) 401s that routes pass through.
AUTH_REQUIRED_HEADER = "X-HomeSentinel-Auth"
SSE_EVENTS_PATH = "/api/sse/events"
SSE_TOKEN_TTL_SECONDS = 60
_used_sse_tokens: dict = {}  # nonce -> expiry, kept until the token would have expired anyway


def _sign_sse_payload(payload: str) -> str:
    return hmac.new(HOMESENTINEL_API_KEY.encode(), b"sse-token:" + payload.encode(), sha256).hexdigest()


def issue_sse_token(now: float = None):
    """Return a token for one SSE connection, or None when auth is disabled."""
    if not HOMESENTINEL_API_KEY:
        return None
    now = time.time() if now is None else now
    payload = f"{int(now) + SSE_TOKEN_TTL_SECONDS}.{secrets.token_urlsafe(16)}"
    return f"{payload}.{_sign_sse_payload(payload)}"


def consume_sse_token(token: str, now: float = None) -> bool:
    """Validate an SSE token and mark it used. Each token opens at most one stream."""
    if not HOMESENTINEL_API_KEY or not token:
        return False
    now = time.time() if now is None else now
    for nonce, expiry in list(_used_sse_tokens.items()):
        if expiry < now:
            del _used_sse_tokens[nonce]
    parts = token.split(".")
    if len(parts) != 3:
        return False
    expiry_text, nonce, signature = parts
    if not hmac.compare_digest(signature, _sign_sse_payload(f"{expiry_text}.{nonce}")):
        return False
    try:
        expiry = int(expiry_text)
    except ValueError:
        return False
    if expiry < now or nonce in _used_sse_tokens:
        return False
    _used_sse_tokens[nonce] = expiry
    return True


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces X-API-Key header on /api/* routes.

    Skips auth for:
      - /oauth/* (Alexa account linking)
      - /static/* (frontend assets)
      - /health (uptime checks)
      - Non-API paths (frontend SPA)
      - When HOMESENTINEL_API_KEY env var is empty (auth disabled)
    """

    async def dispatch(self, request: Request, call_next):
        # 2026-03-12: Skip auth if no API key configured (backwards compat)
        if not HOMESENTINEL_API_KEY:
            return await call_next(request)

        path = request.url.path

        # Skip auth for non-API paths
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip auth for health endpoint
        if path == "/api/health":
            return await call_next(request)

        # Skip auth for OAuth paths (handled under /oauth/ prefix, but check just in case)
        if path.startswith("/oauth/") or path.startswith("/static/"):
            return await call_next(request)

        # 2026-03-12: Require X-API-Key header on all /api/* requests
        provided_key = request.headers.get("X-API-Key", "")
        # SSE only: accept a one-time token from POST /api/sse/token instead of the header.
        if (
            not provided_key
            and path == SSE_EVENTS_PATH
            and request.method == "GET"
            and consume_sse_token(request.query_params.get("token", ""))
        ):
            return await call_next(request)
        if not provided_key or not hmac.compare_digest(provided_key, HOMESENTINEL_API_KEY):
            client_host = request.client.host if request.client else "unknown"
            logger.warning("API key auth failed for %s from %s", path, client_host)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Set X-API-Key header."},
                headers={AUTH_REQUIRED_HEADER: "api-key"},
            )

        return await call_next(request)
