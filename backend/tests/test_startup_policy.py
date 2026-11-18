"""Tests for backend/startup_policy.py (bind host, TLS and auth fail-closed policy)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from startup_policy import (  # noqa: E402
    DEFAULT_HOST,
    StartupPolicyError,
    describe_startup_config,
    is_loopback_host,
    resolve_startup_config,
)

KEY = "s3cr3t-key-value"


def _certs(tmp_path, cert=True, key=True):
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    if cert:
        cert_file.write_text("cert")
    if key:
        key_file.write_text("key")
    return str(cert_file), str(key_file)


def test_default_host_is_loopback(tmp_path):
    config = resolve_startup_config({}, *_certs(tmp_path, False, False))
    assert DEFAULT_HOST == "127.0.0.1"
    assert config.host == "127.0.0.1"
    assert config.port == 8443
    assert config.loopback is True


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "[::1]", "localhost", "LOCALHOST"])
def test_loopback_hosts(host):
    assert is_loopback_host(host) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.12.5", "example.com", "", "localhost.evil.com"])
def test_non_loopback_hosts(host):
    assert is_loopback_host(host) is False


def test_loopback_without_key_or_certs_is_allowed(tmp_path):
    config = resolve_startup_config({}, *_certs(tmp_path, False, False))
    assert config.tls_enabled is False
    assert config.auth_enabled is False
    assert config.ssl_certfile is None and config.ssl_keyfile is None


def test_loopback_with_key_and_certs(tmp_path):
    cert_file, key_file = _certs(tmp_path)
    config = resolve_startup_config({"HOMESENTINEL_API_KEY": KEY}, cert_file, key_file)
    assert config.tls_enabled is True
    assert config.auth_enabled is True
    assert config.ssl_certfile == cert_file
    assert config.ssl_keyfile == key_file


def test_bracketed_ipv6_loopback_is_unwrapped(tmp_path):
    config = resolve_startup_config({"HOMESENTINEL_HOST": "[::1]"}, *_certs(tmp_path, False, False))
    assert config.host == "::1"
    assert config.loopback is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.12.5"])
def test_non_loopback_without_key_is_refused(tmp_path, host):
    with pytest.raises(StartupPolicyError, match="HOMESENTINEL_API_KEY"):
        resolve_startup_config({"HOMESENTINEL_HOST": host}, *_certs(tmp_path))


def test_non_loopback_without_certs_is_refused(tmp_path):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": KEY}
    with pytest.raises(StartupPolicyError, match="plaintext"):
        resolve_startup_config(env, *_certs(tmp_path, False, False))


def test_non_loopback_with_only_cert_is_refused(tmp_path):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": KEY}
    cert_file, key_file = _certs(tmp_path, cert=True, key=False)
    with pytest.raises(StartupPolicyError) as exc:
        resolve_startup_config(env, cert_file, key_file)
    assert key_file in str(exc.value)
    assert cert_file not in str(exc.value)


def test_non_loopback_with_key_and_certs_is_allowed(tmp_path):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": KEY}
    config = resolve_startup_config(env, *_certs(tmp_path))
    assert config.loopback is False
    assert config.tls_enabled is True
    assert config.auth_enabled is True
    assert config.insecure_override is False


@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_insecure_override_allows_non_loopback(tmp_path, value):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_ALLOW_INSECURE_BIND": value}
    config = resolve_startup_config(env, *_certs(tmp_path, False, False))
    assert config.insecure_override is True
    assert config.loopback is False
    assert config.tls_enabled is False
    assert config.auth_enabled is False


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_insecure_override_falsy_values_do_not_override(tmp_path, value):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_ALLOW_INSECURE_BIND": value}
    with pytest.raises(StartupPolicyError):
        resolve_startup_config(env, *_certs(tmp_path))


def test_whitespace_api_key_counts_as_absent(tmp_path):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": "   "}
    with pytest.raises(StartupPolicyError, match="HOMESENTINEL_API_KEY"):
        resolve_startup_config(env, *_certs(tmp_path))


def test_whitespace_host_uses_default(tmp_path):
    config = resolve_startup_config({"HOMESENTINEL_HOST": "  "}, *_certs(tmp_path, False, False))
    assert config.host == "127.0.0.1"


@pytest.mark.parametrize("port", ["abc", "0", "70000"])
def test_invalid_port_is_refused(tmp_path, port):
    with pytest.raises(StartupPolicyError, match="BACKEND_PORT"):
        resolve_startup_config({"BACKEND_PORT": port}, *_certs(tmp_path))


def test_custom_port(tmp_path):
    config = resolve_startup_config({"BACKEND_PORT": "9443"}, *_certs(tmp_path))
    assert config.port == 9443


def test_describe_reports_modes_without_key(tmp_path):
    env = {"HOMESENTINEL_HOST": "0.0.0.0", "HOMESENTINEL_API_KEY": KEY}
    line = describe_startup_config(resolve_startup_config(env, *_certs(tmp_path)))
    assert "bind=0.0.0.0:8443" in line
    assert "(non-loopback)" in line
    assert "tls=on" in line
    assert "auth=on" in line
    assert KEY not in line

    empty = tmp_path / "empty"
    empty.mkdir()
    line = describe_startup_config(resolve_startup_config({}, *_certs(empty, False, False)))
    assert "bind=127.0.0.1:8443 (loopback)" in line
    assert "tls=off" in line
    assert "auth=off" in line
