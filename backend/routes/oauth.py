"""
HomeSentinel OAuth Server for Alexa Account Linking

Minimal OAuth 2.0 Authorization Code Grant flow.
This is a personal/dev skill — no real user auth needed.
"""

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
# 2026-03-12: Moved secret to env var — default kept for backwards compat
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "cnvTIecW1vZHaByRG0vtTd_X2OCY0b7HKrcA5SPvpMU")

# In-memory stores (sufficient for personal dev skill)
_auth_codes: dict[str, dict] = {}   # code -> {redirect_uri, expires, client_id}
_access_tokens: dict[str, dict] = {}  # token -> {expires, client_id}
_refresh_tokens: dict[str, dict] = {}  # token -> {expires, client_id}


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