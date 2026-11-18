"""Deployment config keeps LAN exposure explicit and documented."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read(name):
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _backend_environment():
    """Active entries of services.backend.environment in docker-compose.yml (no yaml dependency)."""
    lines = _read("docker-compose.yml").splitlines()
    service = lines.index("  backend:")
    env_start = lines.index("    environment:", service)
    entries = []
    for line in lines[env_start + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith("      "):
            break  # next key of the backend service, or next service
        entries.append(stripped)
    return entries


def test_compose_sets_host_and_requires_api_key():
    backend = _backend_environment()
    assert "- HOMESENTINEL_HOST=0.0.0.0" in backend
    assert any(line.startswith("- HOMESENTINEL_API_KEY=${HOMESENTINEL_API_KEY:?") for line in backend)
    assert "BACKEND_HOST" not in _read("docker-compose.yml")


def test_env_example_defaults_to_loopback():
    env_example = _read(".env.example")
    assert "HOMESENTINEL_HOST=127.0.0.1" in env_example
    assert "BACKEND_HOST" not in env_example


def test_docs_list_new_env_vars():
    for name in ("README.md", "CLAUDE.md"):
        text = _read(name)
        assert "`HOMESENTINEL_HOST`" in text, name
        assert "`HOMESENTINEL_ALLOW_INSECURE_BIND`" in text, name
