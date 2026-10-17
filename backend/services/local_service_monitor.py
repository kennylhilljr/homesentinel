"""Read-only local listener discovery and tightly allowlisted service controls."""

from __future__ import annotations

import os
import re
import ssl
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional


DEFAULT_CONFIGS = (
    {"id": "homesentinel-frontend", "name": "HomeSentinel Frontend", "port": 2026,
     "health_url": "http://127.0.0.1:2026/"},
    {"id": "homesentinel-backend", "name": "HomeSentinel Backend", "port": 8443,
     "health_url": "https://127.0.0.1:8443/api/health"},
)


class LocalServiceMonitor:
    def __init__(self, db: Any, *, runner: Callable[..., Any] = subprocess.run,
                 health_checker: Optional[Callable[[str], tuple[bool, float, Optional[str]]]] = None,
                 configs: Optional[Iterable[dict[str, Any]]] = None, retention: int = 5000):
        self.db = db
        self.runner = runner
        self.health_checker = health_checker or self._check_health
        self.configs = tuple(dict(item) for item in (configs or DEFAULT_CONFIGS))
        self.retention = max(1, int(retention))

    @staticmethod
    def _check_health(url: str) -> tuple[bool, float, Optional[str]]:
        started = time.monotonic()
        try:
            context = ssl._create_unverified_context() if url.startswith("https://") else None
            with urllib.request.urlopen(url, timeout=2, context=context) as response:
                ok = 200 <= response.status < 400
            return ok, round((time.monotonic() - started) * 1000, 1), None if ok else f"HTTP {response.status}"
        except Exception as exc:
            return False, round((time.monotonic() - started) * 1000, 1), type(exc).__name__

    def _listeners(self) -> list[dict[str, Any]]:
        try:
            result = self.runner(
                ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], capture_output=True,
                text=True, timeout=3, check=False,
            )
        except (subprocess.SubprocessError, OSError):
            return []
        if result.returncode not in (0, 1):
            return []
        listeners = []
        for line in result.stdout.splitlines()[1:]:
            fields = line.split(None, 8)
            if len(fields) < 9:
                continue
            match = re.search(r"TCP\s+(.+):(\d+)\s+\(LISTEN\)$", line)
            if not match:
                continue
            try:
                pid, port = int(fields[1]), int(match.group(2))
            except ValueError:
                continue
            listeners.append({"pid": pid, "process": fields[0][:256], "protocol": "tcp",
                              "bind_address": match.group(1), "port": port, "project_path": None})
        return listeners

    def snapshot(self) -> dict[str, Any]:
        listeners = self._listeners()
        by_port: dict[int, list[dict[str, Any]]] = {}
        for listener in listeners:
            by_port.setdefault(listener["port"], []).append(listener)
        configured_ports = {int(item["port"]) for item in self.configs}
        services = []
        for config in self.configs:
            port_listeners = by_port.get(int(config["port"]), [])
            listener = port_listeners[0] if port_listeners else None
            service = {"id": config["id"], "name": config["name"], "port": int(config["port"]),
                       "protocol": "tcp", "pid": None, "process": None, "bind_address": None,
                       "project_path": None, "response_time_ms": None, "health_error": None,
                       "uptime_seconds": None, "connections": 0, "expected": True,
                       "controllable": self._is_controllable(config)}
            if listener:
                service.update(listener)
                if config.get("health_url"):
                    ok, elapsed, error = self.health_checker(config["health_url"])
                    service.update(response_time_ms=elapsed, health_error=error,
                                   status="healthy" if ok else "degraded")
                else:
                    service["status"] = "listening"
            else:
                service["status"] = "down"
            service["health_status"] = service["status"]
            services.append(service)
        for listener in listeners:
            matches = by_port[listener["port"]]
            is_primary = listener["port"] in configured_ports and listener is matches[0]
            if not is_primary:
                services.append({"id": f"tcp-{listener['port']}-{listener['pid']}",
                                 "name": listener["process"], "status": "listening",
                                 "health_status": "listening", "response_time_ms": None,
                                 "health_error": None, "uptime_seconds": None,
                                 "connections": 0, "expected": False,
                                 "controllable": False, **listener})
        services.sort(key=lambda item: item["port"])
        self._record(services)
        self._enrich_history(services)
        statuses = ("healthy", "degraded", "down", "listening")
        summary = {"total": len(services),
                   **{state: sum(s["status"] == state for s in services) for state in statuses},
                   "unexpected": sum(not s["expected"] for s in services),
                   "conflicts": sum(len(items) > 1 for items in by_port.values())}
        return {"services": services, "summary": summary,
                "updated_at": datetime.now(timezone.utc).isoformat()}

    def _record(self, services: list[dict[str, Any]]) -> None:
        with self.db.write_connection() as conn:
            for service in services:
                previous = conn.execute(
                    "SELECT status FROM local_service_samples WHERE service_id = ? ORDER BY id DESC LIMIT 1",
                    (service["id"],),
                ).fetchone()
                old_status = previous[0] if previous else None
                status = service["status"]
                if old_status != status:
                    conn.execute(
                        "INSERT INTO local_service_events(service_id,event_type,old_status,new_status,detail) VALUES(?,?,?,?,?)",
                        (service["id"], f"service_{status}", old_status, status, service.get("health_error")),
                    )
                conn.execute(
                    "INSERT INTO local_service_samples(service_id,status,response_time_ms,connection_count) VALUES(?,?,?,?)",
                    (service["id"], status, service.get("response_time_ms"), service["connections"]),
                )
            conn.execute("DELETE FROM local_service_samples WHERE id NOT IN (SELECT id FROM local_service_samples ORDER BY id DESC LIMIT ?)", (self.retention,))
            conn.execute("DELETE FROM local_service_events WHERE id NOT IN (SELECT id FROM local_service_events ORDER BY id DESC LIMIT ?)", (self.retention,))
            conn.commit()

    def _enrich_history(self, services: list[dict[str, Any]]) -> None:
        with self.db.get_connection() as conn:
            for service in services:
                samples = conn.execute(
                    "SELECT status,response_time_ms,connection_count,sampled_at FROM local_service_samples WHERE service_id = ? ORDER BY id DESC LIMIT 30",
                    (service["id"],),
                ).fetchall()
                event = conn.execute(
                    "SELECT created_at FROM local_service_events WHERE service_id = ? ORDER BY id DESC LIMIT 1",
                    (service["id"],),
                ).fetchone()
                service["history"] = [dict(row) for row in reversed(samples)]
                service["last_changed"] = event[0] if event else None

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id,service_id,event_type,old_status,new_status,detail,created_at FROM local_service_events ORDER BY id DESC LIMIT ?",
                (min(max(int(limit), 1), 1000),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_traffic(self, limit: int = 300) -> list[dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id,service_id,status,response_time_ms,connection_count,sampled_at FROM local_service_samples ORDER BY id DESC LIMIT ?",
                (min(max(int(limit), 1), 5000),),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _valid_argv(value: Any) -> bool:
        return isinstance(value, list) and bool(value) and all(
            isinstance(part, str) and bool(part) and "\x00" not in part for part in value
        )

    def _is_controllable(self, config: dict[str, Any]) -> bool:
        enabled = os.getenv("HOMESENTINEL_SERVICE_CONTROLS_ENABLED", "").lower() == "true"
        return enabled and any(self._valid_argv(config.get(f"{action}_argv")) for action in ("restart", "stop"))

    def control(self, service_id: str, action: str) -> dict[str, Any]:
        if os.getenv("HOMESENTINEL_SERVICE_CONTROLS_ENABLED", "").lower() != "true":
            raise PermissionError("Service controls are disabled")
        config = next((item for item in self.configs if item["id"] == service_id), None)
        if config is None:
            raise KeyError(service_id)
        argv = config.get(f"{action}_argv")
        if action not in ("restart", "stop") or not self._valid_argv(argv):
            raise PermissionError(f"{action} is not allowlisted for this service")
        result = self.runner(argv, capture_output=True, text=True, timeout=10, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "service command failed")[:500])
        return {"success": True, "service_id": service_id, "action": action}
