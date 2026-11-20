"""SSE auth: EventSource can't send X-API-Key, so /api/sse/events takes a one-time token."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import auth as auth_middleware
from middleware.auth import APIKeyAuthMiddleware
from routes import sse as sse_routes

KEY = "test-key-not-a-secret"


def _app():
    app = FastAPI()
    app.add_middleware(APIKeyAuthMiddleware)
    app.post("/api/sse/token")(sse_routes.sse_token)

    # Stand-in for the infinite stream; the middleware decision is what's under test.
    @app.get("/api/sse/events")
    async def events():
        return {"stream": "ok"}

    @app.get("/api/devices")
    async def devices():
        return {"devices": []}

    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", KEY)
    monkeypatch.setattr(auth_middleware, "_used_sse_tokens", {})
    return TestClient(_app())


def _token(client):
    response = client.post("/api/sse/token", headers={"X-API-Key": KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == auth_middleware.SSE_TOKEN_TTL_SECONDS
    assert KEY not in body["token"]
    return body["token"]


def test_token_endpoint_requires_api_key(client):
    assert client.post("/api/sse/token").status_code == 401
    assert client.post("/api/sse/token", headers={"X-API-Key": "wrong"}).status_code == 401


def test_events_without_key_or_token_is_401(client):
    response = client.get("/api/sse/events")
    assert response.status_code == 401
    assert response.headers[auth_middleware.AUTH_REQUIRED_HEADER] == "api-key"


def test_events_with_header_key_still_works(client):
    assert client.get("/api/sse/events", headers={"X-API-Key": KEY}).status_code == 200


def test_events_accepts_issued_token_once(client):
    token = _token(client)
    assert client.get("/api/sse/events", params={"token": token}).status_code == 200
    assert client.get("/api/sse/events", params={"token": token}).status_code == 401


def test_api_key_in_query_string_is_not_accepted(client):
    assert client.get("/api/sse/events", params={"token": KEY}).status_code == 401
    assert client.get("/api/sse/events", params={"api_key": KEY}).status_code == 401


def test_token_only_opens_the_sse_stream(client):
    token = _token(client)
    assert client.get("/api/devices", params={"token": token}).status_code == 401
    assert client.post("/api/sse/token", params={"token": token}).status_code == 401
    # Not consumed by the rejected attempts above.
    assert client.get("/api/sse/events", params={"token": token}).status_code == 200


def test_expired_token_is_rejected(client):
    token = auth_middleware.issue_sse_token(now=1000.0)
    assert not auth_middleware.consume_sse_token(token, now=1000.0 + auth_middleware.SSE_TOKEN_TTL_SECONDS + 1)
    assert auth_middleware.consume_sse_token(token, now=1000.0 + auth_middleware.SSE_TOKEN_TTL_SECONDS)


def test_tampered_or_malformed_tokens_are_rejected(client):
    token = auth_middleware.issue_sse_token()
    expiry, nonce, signature = token.split(".")
    forged = f"{int(expiry) + 3600}.{nonce}.{signature}"
    for bad in (forged, f"{expiry}.{nonce}.{'0' * len(signature)}", "abc", "a.b.c", "", f"x.{nonce}.{signature}"):
        assert not auth_middleware.consume_sse_token(bad), bad


def test_token_signed_with_another_key_is_rejected(client, monkeypatch):
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", "other-key")
    token = auth_middleware.issue_sse_token()
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", KEY)
    assert not auth_middleware.consume_sse_token(token)


def test_used_tokens_are_pruned_after_expiry(client):
    token = auth_middleware.issue_sse_token(now=1000.0)
    assert auth_middleware.consume_sse_token(token, now=1000.0)
    assert len(auth_middleware._used_sse_tokens) == 1
    auth_middleware.consume_sse_token("a.b.c", now=5000.0)
    assert auth_middleware._used_sse_tokens == {}


def test_auth_disabled_needs_no_token(monkeypatch):
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", "")
    client = TestClient(_app())
    assert client.post("/api/sse/token").json() == {"token": None, "expires_in": None}
    assert client.get("/api/sse/events").status_code == 200
    assert not auth_middleware.consume_sse_token("anything")


def test_real_app_registers_token_route():
    import main

    routes = {(route.path, method) for route in main.app.routes for method in getattr(route, "methods", ())}
    assert ("/api/sse/token", "POST") in routes
    assert ("/api/sse/events", "GET") in routes


def test_real_app_exposes_auth_marker_to_cross_origin_dashboard(monkeypatch):
    import main

    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", KEY)
    origin = main.ALLOWED_ORIGINS[0]
    response = TestClient(main.app).post("/api/sse/token", headers={"Origin": origin})
    assert response.status_code == 401
    assert response.headers[auth_middleware.AUTH_REQUIRED_HEADER] == "api-key"
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert auth_middleware.AUTH_REQUIRED_HEADER.lower() in exposed


@pytest.mark.parametrize("raw, expected", [("  k-123  ", "k-123"), ("   ", ""), ("", "")])
def test_middleware_key_is_stripped_like_startup_policy(raw, expected):
    import os
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "HOMESENTINEL_API_KEY": raw}
    out = subprocess.run(
        [sys.executable, "-c", "from middleware import auth; print(repr(auth.HOMESENTINEL_API_KEY))"],
        cwd=backend, env=env, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == repr(expected)
