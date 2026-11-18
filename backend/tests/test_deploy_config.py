"""Deployment config keeps LAN exposure explicit and documented."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read(name):
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _backend_service_lines():
    """Non-comment lines of the backend service block in docker-compose.yml (no yaml dependency)."""
    lines = _read("docker-compose.yml").splitlines()
    start = lines.index("  backend:")
    block = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith("    "):
            break  # next service or top-level key
        if line.strip() and not line.strip().startswith("#"):
            block.append(line.strip())
    return block


def test_compose_sets_host_and_requires_api_key():
    backend = _backend_service_lines()
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
