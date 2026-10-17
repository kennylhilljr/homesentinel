"""
HomeSentinel OAuth Server for Alexa Account Linking

Minimal OAuth 2.0 Authorization Code Grant flow.
This is a personal/dev skill — no real user auth needed.
"""

import asyncio
import os
import secrets
import time
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth"])

# Config — must match what's in the Alexa Developer Console
CLIENT_ID = "homesentinel"
# OAUTH_CLIENT_SECRET must be set in the environment — no hardcoded default.
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
if not CLIENT_SECRET:
    logger.warning("OAUTH_CLIENT_SECRET not set — OAuth token endpoint will reject all requests")

# Comma-separated list of allowed redirect_uri prefixes. If unset, all are allowed
# with a warning (preserves backwards-compat for personal-skill default).
_redirect_allowlist_raw = os.getenv("OAUTH_REDIRECT_URI_ALLOWLIST", "").strip()
REDIRECT_URI_ALLOWLIST: list[str] = (
    [s.strip() for s in _redirect_allowlist_raw.split(",") if s.strip()]
    if _redirect_allowlist_raw
    else []
)
if not REDIRECT_URI_ALLOWLIST:
    logger.warning(
        "OAUTH_REDIRECT_URI_ALLOWLIST not set — any redirect_uri is accepted. "
        "Set this env var to a comma-separated list of allowed prefixes to prevent code-theft."
    )


def _redirect_uri_allowed(redirect_uri: str) -> bool:
    if not REDIRECT_URI_ALLOWLIST:
        return True
    return any(redirect_uri.startswith(prefix) for prefix in REDIRECT_URI_ALLOWLIST)

# In-memory stores (sufficient for personal dev skill)
_auth_codes: dict[str, dict] = {}   # code -> {redirect_uri, expires, client_id}
_access_tokens: dict[str, dict] = {}  # token -> {expires, client_id}
_refresh_tokens: dict[str, dict] = {}  # token -> {expires, client_id}


async def _expire_oauth_entries():
    """Background sweep that drops expired OAuth codes/tokens to prevent unbounded growth."""
    while True:
        try:
            await asyncio.sleep(300)
            now = time.time()
            for store in (_auth_codes, _access_tokens, _refresh_tokens):
                for key in [k for k, v in store.items() if v.get("expires", 0) < now]:
                    store.pop(key, None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("OAuth expiry sweep error: %s", e)


def start_oauth_cleanup_task() -> asyncio.Task:
    """Start the background expiry sweep. Call from app startup."""
    return asyncio.create_task(_expire_oauth_entries())


@router.get("/authorize")
async def authorize(
    client_id: str,
    response_type: str,
    redirect_uri: str,
    state: str = "",
    scope: str = "",
):
    """OAuth authorization endpoint — shows consent page and redirects with auth code."""
    if client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only 'code' response_type supported")
    if not _redirect_uri_allowed(redirect_uri):
        logger.warning("OAuth authorize: rejected redirect_uri=%s (not in allowlist)", redirect_uri)
        raise HTTPException(status_code=400, detail="redirect_uri is not allowed")

    # Generate auth code
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "redirect_uri": redirect_uri,
        "expires": time.time() + 300,  # 5 min
        "client_id": client_id,
    }

    logger.info("OAuth authorize: issuing code for redirect to %s", redirect_uri)

    # Auto-approve (personal skill — no login needed)
    # Build redirect with code and state
    separator = "&" if "?" in redirect_uri else "?"
    redirect_url = f"{redirect_uri}{separator}{urlencode({'code': code, 'state': state})}"

    return RedirectResponse(url=redirect_url)


@router.post("/token")
async def token(request: Request):
    """OAuth token endpoint — exchanges auth code for access + refresh tokens."""
    # Support both form-encoded and JSON
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        data = dict(form)
    else:
        data = await request.json()

    grant_type = data.get("grant_type", "")
    client_id = data.get("client_id", CLIENT_ID)
    client_secret = data.get("client_secret", "")

    # Also check Authorization header (HTTP Basic)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        import base64
        decoded = base64.b64decode(auth_header[6:]).decode()
        if ":" in decoded:
            client_id, client_secret = decoded.split(":", 1)

    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        logger.warning("OAuth token: invalid credentials (client_id=%s)", client_id)
        return JSONResponse(status_code=401, content={"error": "invalid_client"})

    if grant_type == "authorization_code":
        code = data.get("code", "")
        stored = _auth_codes.pop(code, None)

        if not stored or stored["expires"] < time.time():
            return JSONResponse(status_code=400, content={"error": "invalid_grant"})

        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        _access_tokens[access_token] = {
            "expires": time.time() + 3600,
            "client_id": client_id,
        }
        _refresh_tokens[refresh_token] = {
            "expires": time.time() + 86400 * 365,  # 1 year
            "client_id": client_id,
        }

        logger.info("OAuth token: issued access + refresh tokens (auth_code grant)")

        return JSONResponse(content={
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": refresh_token,
        })

    elif grant_type == "refresh_token":
        refresh = data.get("refresh_token", "")
        stored = _refresh_tokens.get(refresh)

        if not stored or stored["expires"] < time.time():
            return JSONResponse(status_code=400, content={"error": "invalid_grant"})

        access_token = secrets.token_urlsafe(32)
        _access_tokens[access_token] = {
            "expires": time.time() + 3600,
            "client_id": client_id,
        }

        logger.info("OAuth token: refreshed access token")

        return JSONResponse(content={
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": refresh,
        })

    return JSONResponse(status_code=400, content={"error": "unsupported_grant_type"})