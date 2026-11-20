"""Tests for main.run_server(): the startup policy is applied before uvicorn starts."""

import logging
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402
from middleware import auth as auth_middleware  # noqa: E402

KEY = "s3cr3t-key-value"
POLICY_VARS = ("HOMESENTINEL_HOST", "HOMESENTINEL_API_KEY", "HOMESENTINEL_ALLOW_INSECURE_BIND", "BACKEND_PORT")


@pytest.fixture
def calls(monkeypatch):
    """Record uvicorn.run calls and start every test from a clean policy environment."""
    for name in POLICY_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", "")
    recorded = []
    monkeypatch.setattr(main.uvicorn, "run", lambda *args, **kwargs: recorded.append((args, kwargs)))
    return recorded


def _enforced_key(monkeypatch, key):
    """Set the key both in the environment and in the middleware that enforces it."""
    monkeypatch.setenv("HOMESENTINEL_API_KEY", key)
    monkeypatch.setattr(auth_middleware, "HOMESENTINEL_API_KEY", key)


def _write_certs(path):
    (path / "cert.pem").write_text("cert")
    (path / "key.pem").write_text("key")


def test_default_binds_localhost_without_tls(tmp_path, calls):
    main.run_server(cert_dir=str(tmp_path))
    assert len(calls) == 1
    kwargs = calls[0][1]
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8443
    assert kwargs["ssl_certfile"] is None
    assert kwargs["ssl_keyfile"] is None


def test_default_binds_localhost_with_tls(tmp_path, calls):
    _write_certs(tmp_path)
    main.run_server(cert_dir=str(tmp_path))
    kwargs = calls[0][1]
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["ssl_certfile"] == str(tmp_path / "cert.pem")
    assert kwargs["ssl_keyfile"] == str(tmp_path / "key.pem")


def test_non_loopback_without_key_exits(tmp_path, calls, monkeypatch):
    _write_certs(tmp_path)
    monkeypatch.setenv("HOMESENTINEL_HOST", "0.0.0.0")
    with pytest.raises(SystemExit) as exc:
        main.run_server(cert_dir=str(tmp_path))
    assert exc.value.code == 1
    assert calls == []


def test_non_loopback_without_certs_exits(tmp_path, calls, monkeypatch):
    monkeypatch.setenv("HOMESENTINEL_HOST", "0.0.0.0")
    _enforced_key(monkeypatch, "k")
    with pytest.raises(SystemExit) as exc:
        main.run_server(cert_dir=str(tmp_path))
    assert exc.value.code == 1
    assert calls == []


def test_env_key_not_enforced_by_middleware_is_refused(tmp_path, calls, monkeypatch):
    """A key that appeared in the env after the middleware loaded does not count as auth."""
    _write_certs(tmp_path)
    monkeypatch.setenv("HOMESENTINEL_HOST", "0.0.0.0")
    monkeypatch.setenv("HOMESENTINEL_API_KEY", KEY)
    with pytest.raises(SystemExit):
        main.run_server(cert_dir=str(tmp_path))
    assert calls == []


def test_non_loopback_with_key_and_certs_starts_without_logging_key(tmp_path, calls, caplog, monkeypatch):
    _write_certs(tmp_path)
    monkeypatch.setenv("HOMESENTINEL_HOST", "0.0.0.0")
    _enforced_key(monkeypatch, KEY)
    with caplog.at_level(logging.INFO):
        main.run_server(cert_dir=str(tmp_path))
    assert calls[0][1]["host"] == "0.0.0.0"
    assert calls[0][1]["ssl_certfile"] == str(tmp_path / "cert.pem")
    assert "bind=0.0.0.0:8443 (non-loopback) tls=on auth=on" in caplog.text
    assert KEY not in caplog.text

    # The app that was started actually enforces the key the policy saw.
    client = TestClient(calls[0][0][0])
    assert client.get("/api/devices").status_code == 401
    assert client.get("/api/devices", headers={"X-API-Key": "wrong"}).status_code == 401
    # The configured key gets past auth (the catch-all then answers 404 for an unknown API path).
    assert client.get("/api/no-such-route", headers={"X-API-Key": KEY}).status_code == 404


def test_insecure_override_starts_and_warns(tmp_path, calls, caplog, monkeypatch):
    monkeypatch.setenv("HOMESENTINEL_HOST", "0.0.0.0")
    monkeypatch.setenv("HOMESENTINEL_ALLOW_INSECURE_BIND", "1")
    with caplog.at_level(logging.INFO):
        main.run_server(cert_dir=str(tmp_path))
    assert calls[0][1]["host"] == "0.0.0.0"
    assert calls[0][1]["ssl_certfile"] is None
    assert "HOMESENTINEL_ALLOW_INSECURE_BIND" in caplog.text
