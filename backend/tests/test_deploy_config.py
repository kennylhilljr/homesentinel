"""Deployment config keeps LAN exposure explicit and documented."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read(name):
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def test_compose_sets_host_and_requires_api_key():
    compose = _read("docker-compose.yml")
    assert "HOMESENTINEL_HOST=0.0.0.0" in compose
    assert "HOMESENTINEL_API_KEY=${HOMESENTINEL_API_KEY:?" in compose
    assert "BACKEND_HOST" not in compose


def test_env_example_defaults_to_loopback():
    env_example = _read(".env.example")
    assert "HOMESENTINEL_HOST=127.0.0.1" in env_example
    assert "BACKEND_HOST" not in env_example


def test_docs_list_new_env_vars():
    for name in ("README.md", "CLAUDE.md"):
        text = _read(name)
        assert "`HOMESENTINEL_HOST`" in text, name
        assert "`HOMESENTINEL_ALLOW_INSECURE_BIND`" in text, name
