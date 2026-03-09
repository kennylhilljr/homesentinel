"""Tests for Deco Alexa name sync endpoint."""

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.deco import router, set_correlation_service, set_deco_service


app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestDecoSyncNamesEndpoint:
    def setup_method(self):
        self.mock_correlation_service = Mock()
        self.mock_deco_service = Mock()
        set_correlation_service(self.mock_correlation_service)
        set_deco_service(self.mock_deco_service)

    def teardown_method(self):
        set_correlation_service(None)
        set_deco_service(None)

    def test_sync_endpoint_success(self):
        self.mock_correlation_service.sync_network_friendly_names_from_alexa.return_value = {
            "success": True,
            "updated": 2,
            "skipped_existing": 1,
            "skipped_missing": 0,
            "failed": 0,
            "total_links": 3,
            "updates": [
                {"network_device_id": "dev-1", "new_name": "Kitchen Light"},
                {"network_device_id": "dev-2", "new_name": "Hall Plug"},
            ],
        }

        response = client.post("/api/deco/sync-names-from-alexa", json={"overwrite_existing": False})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated"] == 2
        self.mock_correlation_service.sync_network_friendly_names_from_alexa.assert_called_once_with(
            overwrite_existing=False
        )

    def test_sync_endpoint_overwrite_true(self):
        self.mock_correlation_service.sync_network_friendly_names_from_alexa.return_value = {
            "success": True,
            "updated": 1,
            "skipped_existing": 0,
            "skipped_missing": 0,
            "failed": 0,
            "total_links": 1,
            "updates": [{"network_device_id": "dev-1", "new_name": "Office PC"}],
        }

        response = client.post("/api/deco/sync-names-from-alexa", json={"overwrite_existing": True})

        assert response.status_code == 200
        self.mock_correlation_service.sync_network_friendly_names_from_alexa.assert_called_once_with(
            overwrite_existing=True
        )

    def test_sync_endpoint_service_not_initialized(self):
        set_correlation_service(None)

        response = client.post("/api/deco/sync-names-from-alexa", json={"overwrite_existing": False})

        assert response.status_code == 500
        assert "Correlation service not initialized" in response.json().get("detail", "")
