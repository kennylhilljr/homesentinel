"""Tests for main.run_server(): the startup policy is applied before uvicorn starts."""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402

KEY = "s3cr3t-key-value"


@pytest.fixture
def calls(monkeypatch):
    recorded = []
    monkeypatch.setattr(main.uvicorn, "run", lambda *args, **kwargs: recorded.append((args, kwargs)))
    return recorded


def _write_certs(path):
    (path / "cert.pem").write_text("cert")
    (path / "key.pem").write_text("key")


def test_default_binds_localhost_without_tls(tmp_path, calls):
    main.run_server(env={}, cert_dir=str(tmp_path))
    assert len(calls) == 1
    kwargs = calls[0][1]
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8443
    assert kwargs["ssl_certfile"] is None
    assert kwargs["ssl_keyfile"] is None


def test_default_binds_localhost_with_tls(tmp_path, calls):
    _write_certs(tmp_path)
    main.run_server(env={}, cert_dir=str(tmp_path))
    kwargs = calls[0][1]
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["ssl_certfile"] == str(tmp_path / "cert.pem")
    assert kwargs["ssl_keyfile"] == str(tmp_path / "key.pem")


def test_non_loopback_without_key_exits(tmp_path, calls):
    _write_certs(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main.run_server(env={"HOMESENTINEL_HOST": "0.0.0.0"}, cert_dir=str(tmp_path))
    assert exc.value.code == 1
    assert calls == []


def test_non_loopback_without_certs_exits(tmp_path, calls):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": "k"}
    with pytest.raises(SystemExit) as exc:
        main.run_server(env=env, cert_dir=str(tmp_path))
    assert exc.value.code == 1
    assert calls == []


def test_non_loopback_with_key_and_certs_starts_without_logging_key(tmp_path, calls, caplog):
    _write_certs(tmp_path)
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": KEY}
    with caplog.at_level(logging.INFO):
        main.run_server(env=env, cert_dir=str(tmp_path))
    assert calls[0][1]["host"] == "0.0.0.0"
    assert calls[0][1]["ssl_certfile"] == str(tmp_path / "cert.pem")
    assert "bind=0.0.0.0:8443 (non-loopback) tls=on auth=on" in caplog.text
    assert KEY not in caplog.text


def test_insecure_override_starts_and_warns(tmp_path, calls, caplog):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_ALLOW_INSECURE_BIND": "1"}
    with caplog.at_level(logging.INFO):
        main.run_server(env=env, cert_dir=str(tmp_path))
    assert calls[0][1]["host"] == "0.0.0.0"
    assert calls[0][1]["ssl_certfile"] is None
    assert "HOMESENTINEL_ALLOW_INSECURE_BIND" in caplog.text
