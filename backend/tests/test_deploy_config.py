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


def _service_block(service):
    """Raw lines of services.<service> in docker-compose.yml, comments skipped."""
    lines = [line for line in _read("docker-compose.yml").splitlines() if not line.strip().startswith("#")]
    start = lines.index(f"  {service}:")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= 2),
        len(lines),
    )
    return [line.strip() for line in lines[start + 1:end]]


def test_compose_build_contexts_point_at_existing_dockerfiles():
    backend = _service_block("backend")
    assert "context: ." in backend
    assert "dockerfile: backend/Dockerfile" in backend
    frontend = _service_block("frontend")
    assert "context: ./frontend" in frontend
    assert "dockerfile: Dockerfile" in frontend
    assert (REPO_ROOT / "backend" / "Dockerfile").is_file()
    assert (REPO_ROOT / "frontend" / "Dockerfile").is_file()
    assert not any(line.startswith("container_name:") for line in backend + frontend)


def test_backend_image_bundles_dashboard_where_main_serves_it():
    dockerfile = _read("backend/Dockerfile")
    assert "RUN npm run build" in dockerfile
    assert "COPY --from=frontend /src/frontend/build /app/frontend/build" in dockerfile
    assert "WORKDIR /app/backend" in dockerfile
    assert 'CMD ["python", "main.py"]' in dockerfile
    for tool in ("curl", "arp-scan", "nmap", "net-tools"):
        assert tool in dockerfile, tool
    # main.py resolves the build dir relative to the backend dir.
    assert '_BACKEND_DIR.parent / "frontend" / "build"' in _read("backend/main.py")


def test_backend_mounts_keep_build_visible_and_certs_read_only():
    volumes = _service_list("backend", "volumes")
    assert volumes == ["./backend:/app/backend", "./backend/certs:/app/backend/certs:ro"]
    assert not any(v.split(":")[1].startswith("/app/frontend") for v in volumes)


def test_backend_healthcheck_fails_on_http_errors():
    assert 'test: ["CMD", "curl", "-f", "-k", "https://localhost:8443/api/health"]' in _service_block("backend")


def test_frontend_proxy_target_from_env():
    frontend = _service_list("frontend", "environment")
    assert "HOMESENTINEL_PROXY_TARGET=https://backend:8443" in frontend
    assert not any(item.startswith("REACT_APP_") for item in frontend)
    vite = _read("frontend/vite.config.js")
    assert "process.env.HOMESENTINEL_PROXY_TARGET" in vite
    assert "'https://localhost:8443'" in vite
    assert "secure: false" in vite


def test_dockerignore_excludes_secrets_and_local_state():
    entries = set(_read(".dockerignore").splitlines())
    for pattern in ("**/.env", "**/.credential_key", "**/certs", "**/*.db", "**/node_modules", "frontend/build", ".git"):
        assert pattern in entries, pattern
    frontend_entries = set(_read("frontend/.dockerignore").splitlines())
    for pattern in (".env", "node_modules", "build"):
        assert pattern in frontend_entries, pattern


def test_ci_runs_docker_smoke_test():
    ci = _read(".github/workflows/ci.yml")
    assert "  docker:" in ci
    for step in ("docker compose build", "docker compose up -d", "curl -fk https://localhost:8443/api/health",
                 "curl -fk https://localhost:8443/", "docker compose down"):
        assert step in ci, step
