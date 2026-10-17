import os
import sys
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes import local_services


def client(service):
    app = FastAPI()
    app.include_router(local_services.router)
    local_services.set_local_service_monitor(service)
    return TestClient(app)


def test_inventory_events_and_traffic_routes():
    service = mock.Mock()
    service.snapshot.return_value = {"services": [], "summary": {"total": 0}, "updated_at": "now"}
    service.get_events.return_value = []
    service.get_traffic.return_value = []
    api = client(service)
    assert api.get("/api/local-services").status_code == 200
    assert api.get("/api/local-services/events?limit=4").json() == {"events": []}
    assert api.get("/api/local-services/traffic?limit=4").json() == {"samples": []}


def test_control_error_mapping():
    service = mock.Mock()
    api = client(service)
    service.control.side_effect = PermissionError("disabled")
    assert api.post("/api/local-services/api/restart").status_code == 403
    service.control.side_effect = KeyError("unknown")
    assert api.post("/api/local-services/nope/stop").status_code == 404

