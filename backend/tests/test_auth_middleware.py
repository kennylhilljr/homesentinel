"""APIKeyAuthMiddleware edge cases."""
import asyncio

from starlette.requests import Request

from middleware import auth as auth_middleware
from middleware.auth import AUTH_REQUIRED_HEADER, APIKeyAuthMiddleware

KEY = "test-key-not-a-secret"


def _request_without_client():
    # Unix-socket and some ASGI servers leave scope["client"] unset.
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/devices",
        "raw_path": b"/api/devices",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("localhost", 80),
    }
    return Request(scope)


def test_failed_auth_without_client_is_401_not_500(monkeypatch):
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", KEY)
    middleware = APIKeyAuthMiddleware(app=None)
    request = _request_without_client()
    assert request.client is None

    async def call_next(_request):
        raise AssertionError("unauthenticated request reached the app")

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 401
    assert response.headers[AUTH_REQUIRED_HEADER] == "api-key"
