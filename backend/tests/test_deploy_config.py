"""Deployment config keeps LAN exposure explicit and documented."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read(name):
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def test_compose_sets_host_and_requires_api_key():
    backend = _service_list("backend", "environment")
    assert "HOMESENTINEL_HOST=0.0.0.0" in backend
    assert any(item.startswith("HOMESENTINEL_API_KEY=${HOMESENTINEL_API_KEY:?") for item in backend)
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


def _service_list(service, key):
    """Items of services.<service>.<key> in docker-compose.yml, comments skipped."""
    lines = [line for line in _read("docker-compose.yml").splitlines() if not line.strip().startswith("#")]
    start = lines.index(f"  {service}:")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= 2),
        len(lines),
    )
    block = lines[start + 1:end]
    items = []
    for line in block[block.index(f"    {key}:") + 1:]:
        if not line.startswith("      - "):
            break
        items.append(line[len("      - "):].strip().strip('"'))
    return items


def test_compose_frontend_published_on_loopback_only():
    assert _service_list("frontend", "ports") == ["127.0.0.1:2026:2026"]
    frontend = _service_list("frontend", "environment")
    assert "HOMESENTINEL_FRONTEND_HOST=0.0.0.0" in frontend
    assert "HOMESENTINEL_ALLOW_INSECURE_BIND=1" in frontend
    assert not any(item.startswith(("HOMESENTINEL_HOST=", "HOMESENTINEL_API_KEY=")) for item in frontend)


def test_docs_list_frontend_host():
    for name in ("README.md", "CLAUDE.md"):
        assert any(line.startswith("| `HOMESENTINEL_FRONTEND_HOST` |") for line in _read(name).splitlines()), name
