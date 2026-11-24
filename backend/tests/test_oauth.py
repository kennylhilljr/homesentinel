"""OAuth account-linking endpoints: fail closed when the secret or redirect allowlist is unset."""
import base64
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import oauth

SECRET = "test-secret-not-real"
REDIRECT = "https://example.test/callback"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(oauth, "CLIENT_SECRET", SECRET)
    monkeypatch.setattr(oauth, "REDIRECT_URI_ALLOWLIST", ["https://example.test/"])
    monkeypatch.setattr(oauth, "_auth_codes", {})
    monkeypatch.setattr(oauth, "_access_tokens", {})
    monkeypatch.setattr(oauth, "_refresh_tokens", {})
    app = FastAPI()
    app.include_router(oauth.router)
    return TestClient(app)


def _authorize(client, redirect_uri=REDIRECT):
    return client.get(
        "/oauth/authorize",
        params={"client_id": oauth.CLIENT_ID, "response_type": "code", "redirect_uri": redirect_uri, "state": "s"},
        follow_redirects=False,
    )


def _code(client):
    response = _authorize(client)
    assert response.status_code in (302, 307)
    return parse_qs(urlparse(response.headers["location"]).query)["code"][0]


def _exchange(client, code, secret=SECRET):
    data = {"grant_type": "authorization_code", "code": code, "client_id": oauth.CLIENT_ID}
    if secret is not None:
        data["client_secret"] = secret
    return client.post("/oauth/token", data=data)


def test_valid_flow_issues_tokens(client):
    response = _exchange(client, _code(client))
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"] and body["refresh_token"]


def test_basic_auth_header_is_accepted(client):
    code = _code(client)
    basic = base64.b64encode(f"{oauth.CLIENT_ID}:{SECRET}".encode()).decode()
    response = client.post(
        "/oauth/token",
        data={"grant_type": "authorization_code", "code": code},
        headers={"Authorization": f"Basic {basic}"},
    )
    assert response.status_code == 200


def test_malformed_basic_auth_header_is_rejected(client):
    response = client.post(
        "/oauth/token",
        data={"grant_type": "authorization_code", "code": "x"},
        headers={"Authorization": "Basic not-base64!!"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": "invalid_client"}


def test_token_rejects_missing_secret_when_secret_unset(client, monkeypatch):
    """Regression for #15: an empty secret used to match a request with no client_secret."""
    code = _code(client)
    monkeypatch.setattr(oauth, "CLIENT_SECRET", "")
    for secret in (None, ""):
        response = _exchange(client, code, secret=secret)
        assert response.status_code == 401
        assert response.json() == {"error": "invalid_client"}
    assert code in oauth._auth_codes  # rejected before the code was consumed


def test_refresh_grant_rejected_when_secret_unset(client, monkeypatch):
    refresh = _exchange(client, _code(client)).json()["refresh_token"]
    monkeypatch.setattr(oauth, "CLIENT_SECRET", "")
    response = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": refresh})
    assert response.status_code == 401


def test_authorize_refused_when_secret_unset(client, monkeypatch):
    monkeypatch.setattr(oauth, "CLIENT_SECRET", "")
    response = _authorize(client)
    assert response.status_code == 503
    assert not oauth._auth_codes


def test_authorize_refused_when_allowlist_unset(client, monkeypatch):
    monkeypatch.setattr(oauth, "REDIRECT_URI_ALLOWLIST", [])
    response = _authorize(client, redirect_uri="https://attacker.test/steal")
    assert response.status_code == 503
    assert not oauth._auth_codes


def test_wrong_secret_rejected(client):
    response = _exchange(client, _code(client), secret="wrong")
    assert response.status_code == 401


def test_redirect_uri_outside_allowlist_rejected(client):
    response = _authorize(client, redirect_uri="https://attacker.test/steal")
    assert response.status_code == 400
    assert not oauth._auth_codes


def test_code_cannot_be_reused(client):
    code = _code(client)
    assert _exchange(client, code).status_code == 200
    response = _exchange(client, code)
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_grant"}


def test_expired_code_rejected(client):
    code = _code(client)
    oauth._auth_codes[code]["expires"] = 0
    response = _exchange(client, code)
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_grant"}


def test_unencodable_secret_is_rejected_not_500(client):
    response = client.post(
        "/oauth/token",
        content='{"grant_type": "authorization_code", "code": "x", "client_secret": "\\ud800"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("body", ["not json", "[1, 2]"])
def test_malformed_json_body(client, monkeypatch, body):
    headers = {"Content-Type": "application/json"}
    assert client.post("/oauth/token", content=body, headers=headers).status_code == 400
    monkeypatch.setattr(oauth, "CLIENT_SECRET", "")
    assert client.post("/oauth/token", content=body, headers=headers).status_code == 401
