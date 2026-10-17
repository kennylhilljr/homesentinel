import os
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.local_service_monitor import LocalServiceMonitor


LSOF = """COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
node 111 bob 22u IPv4 0x0 0t0 TCP *:2026 (LISTEN)
python3 222 bob 9u IPv4 0x0 0t0 TCP 127.0.0.1:8443 (LISTEN)
"""


def database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).parents[1] / "migrations/018_local_service_observability.sql").read_text())
    class TestDatabase:
        reads = 0
        writes = 0

        @contextmanager
        def get_connection(self):
            self.reads += 1
            yield conn

        @contextmanager
        def write_connection(self):
            self.writes += 1
            yield conn

    return TestDatabase()


def test_discovers_and_classifies_listeners_and_health():
    runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, LSOF, ""))
    health = mock.Mock(side_effect=[(True, 12.5, None), (False, 50.0, "timeout")])
    monitor = LocalServiceMonitor(database(), runner=runner, health_checker=health)

    result = monitor.snapshot()

    assert [s["name"] for s in result["services"]] == ["HomeSentinel Frontend", "HomeSentinel Backend"]
    assert [s["status"] for s in result["services"]] == ["healthy", "degraded"]
    assert result["summary"] == {"total": 2, "healthy": 1, "degraded": 1, "down": 0,
                                 "listening": 0, "unexpected": 0, "conflicts": 0}
    assert runner.call_args.kwargs["timeout"] <= 5
    assert result["services"][0]["health_status"] == "healthy"
    assert result["services"][0]["expected"] is True
    assert result["services"][0]["connections"] == 0
    assert result["services"][0]["controllable"] is False
    assert result["services"][0]["history"]


def test_missing_configured_listener_is_down_and_transitions_are_persisted():
    runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n", ""))
    monitor = LocalServiceMonitor(database(), runner=runner, configs=[{
        "id": "api", "name": "API", "port": 9443, "health_url": "https://127.0.0.1:9443/health"
    }])
    first = monitor.snapshot()
    second = monitor.snapshot()

    assert first["services"][0]["status"] == "down"
    events = monitor.get_events(limit=20)
    assert len(events) == 1
    assert events[0]["event_type"] == "service_down"
    assert second["services"][0]["status"] == "down"


def test_timeout_returns_configured_services_as_down():
    runner = mock.Mock(side_effect=subprocess.TimeoutExpired("lsof", 3))
    monitor = LocalServiceMonitor(database(), runner=runner)
    result = monitor.snapshot()
    assert result["summary"]["down"] == 2


def test_controls_are_disabled_and_allowlisted(monkeypatch):
    process = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    config = {"id": "api", "name": "API", "port": 9443, "stop_argv": ["launchctl", "stop", "api"], "restart_argv": ["launchctl", "kickstart", "api"]}
    monitor = LocalServiceMonitor(database(), runner=process, configs=[config])
    monkeypatch.delenv("HOMESENTINEL_SERVICE_CONTROLS_ENABLED", raising=False)
    try:
        monitor.control("api", "stop")
        assert False
    except PermissionError:
        pass
    monkeypatch.setenv("HOMESENTINEL_SERVICE_CONTROLS_ENABLED", "true")
    monitor.control("api", "restart")
    process.assert_called_once_with(config["restart_argv"], capture_output=True, text=True, timeout=10, check=False)
    try:
        monitor.control("unknown", "stop")
        assert False
    except KeyError:
        pass


def test_samples_and_events_have_bounded_retention():
    db = database()
    monitor = LocalServiceMonitor(db, runner=mock.Mock(return_value=subprocess.CompletedProcess([], 0, LSOF, "")), health_checker=lambda _: (True, 1, None), retention=2)
    for _ in range(4):
        monitor.snapshot()
    assert len(monitor.get_traffic(limit=20)) == 2
    assert db.writes == 4
    assert db.reads >= 1


def test_duplicate_port_listeners_are_preserved_and_report_conflict():
    duplicate = LSOF + "python3 333 bob 10u IPv6 0x0 0t0 TCP 127.0.0.1:8443 (LISTEN)\n"
    monitor = LocalServiceMonitor(database(), runner=mock.Mock(return_value=subprocess.CompletedProcess([], 0, duplicate, "")), health_checker=lambda _: (True, 1, None))
    result = monitor.snapshot()
    backend = [item for item in result["services"] if item["port"] == 8443]
    assert len(backend) == 2
    assert backend[0]["expected"] is True
    assert backend[1]["expected"] is False
    assert result["summary"]["conflicts"] == 1
    assert result["summary"]["unexpected"] == 1


def test_control_rejects_non_string_argv(monkeypatch):
    monkeypatch.setenv("HOMESENTINEL_SERVICE_CONTROLS_ENABLED", "true")
    monitor = LocalServiceMonitor(database(), configs=[{"id": "api", "name": "API", "port": 1, "restart_argv": ["ok", 7]}])
    try:
        monitor.control("api", "restart")
        assert False
    except PermissionError:
        pass
