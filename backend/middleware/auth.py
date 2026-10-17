"""
API Key Authentication Middleware for HomeSentinel
# 2026-03-12: Checks X-API-Key header on /api/* requests for optional API key auth.
"""

import hmac
import os
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 2026-03-12: Read API key from env var. If empty/unset, auth is disabled (backwards compat).
HOMESENTINEL_API_KEY = os.getenv("HOMESENTINEL_API_KEY", "")


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
        if not provided_key or not hmac.compare_digest(provided_key, HOMESENTINEL_API_KEY):
            logger.warning("API key auth failed for %s from %s", path, request.client.host)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Set X-API-Key header."},
            )

        return await call_next(request)
