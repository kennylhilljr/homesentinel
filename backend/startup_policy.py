"""
Startup policy for HomeSentinel's backend server.

Decides the bind host, TLS mode and auth mode from the environment, and
fails closed when the server would be exposed beyond localhost without an
API key or TLS certificates.

Stdlib only, no side effects, so it can be unit-tested without starting uvicorn.
"""

import ipaddress
import os
from dataclasses import dataclass
from typing import Mapping, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8443
_TRUTHY = {"1", "true", "yes"}


class StartupPolicyError(Exception):
    """Raised when the requested startup configuration is refused."""


@dataclass(frozen=True)
class StartupConfig:
    host: str
    port: int
    ssl_certfile: Optional[str]
    ssl_keyfile: Optional[str]
    tls_enabled: bool
    auth_enabled: bool
    loopback: bool
    insecure_override: bool


def is_loopback_host(host: str) -> bool:
    """True only for hosts that can't be reached from another machine."""
    value = (host or "").strip()
    if value.lower() == "localhost":
        return True
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def resolve_startup_config(env: Mapping[str, str], cert_file: str, key_file: str) -> StartupConfig:
    """Resolve bind/TLS/auth settings, raising StartupPolicyError when refused."""
    host = (env.get("HOMESENTINEL_HOST") or "").strip() or DEFAULT_HOST
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]  # uvicorn wants a bare IPv6 address

    raw_port = (env.get("BACKEND_PORT") or "").strip() or str(DEFAULT_PORT)
    try:
        port = int(raw_port)
    except ValueError:
        raise StartupPolicyError(f"BACKEND_PORT must be an integer, got {raw_port!r}") from None
    if not 0 < port < 65536:
        raise StartupPolicyError(f"BACKEND_PORT must be between 1 and 65535, got {port}")

    auth_enabled = bool((env.get("HOMESENTINEL_API_KEY") or "").strip())
    insecure_override = (env.get("HOMESENTINEL_ALLOW_INSECURE_BIND") or "").strip().lower() in _TRUTHY
    tls_enabled = os.path.isfile(cert_file) and os.path.isfile(key_file)
    loopback = is_loopback_host(host)

    if not loopback and not insecure_override:
        if not auth_enabled:
            raise StartupPolicyError(
                f"binding to non-loopback host {host} requires HOMESENTINEL_API_KEY "
                "(or set HOMESENTINEL_ALLOW_INSECURE_BIND=1 to override)"
            )
        if not tls_enabled:
            missing = [p for p in (cert_file, key_file) if not os.path.isfile(p)]
            raise StartupPolicyError(
                f"TLS certificate(s) missing: {', '.join(missing)}. A non-loopback bind to {host} "
                "will not fall back to plaintext HTTP (run scripts/gen-cert.sh, "
                "or set HOMESENTINEL_ALLOW_INSECURE_BIND=1 to override)"
            )

    return StartupConfig(
        host=host,
        port=port,
        ssl_certfile=cert_file if tls_enabled else None,
        ssl_keyfile=key_file if tls_enabled else None,
        tls_enabled=tls_enabled,
        auth_enabled=auth_enabled,
        loopback=loopback,
        insecure_override=insecure_override,
    )


def describe_startup_config(config: StartupConfig) -> str:
    """One log line with the effective modes. Never includes the API key."""
    scope = "loopback" if config.loopback else "non-loopback"
    return (
        f"HomeSentinel bind={config.host}:{config.port} ({scope}) "
        f"tls={'on' if config.tls_enabled else 'off'} "
        f"auth={'on' if config.auth_enabled else 'off'} "
        f"insecure_override={'yes' if config.insecure_override else 'no'}"
    )
