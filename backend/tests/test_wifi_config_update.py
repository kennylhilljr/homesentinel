"""
Tests for WiFi configuration updates (PUT /api/deco/wifi-config and
DecoService.update_wifi_config).

WiFi writes are not supported yet: the Deco write payload is unconfirmed and a
wrong SSID/password could disconnect every device. Both the service and the
route must fail cleanly with a clear message and never call the router.
"""

import os
import sys
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import routes.deco as deco_routes  # noqa: E402
from routes.deco import router  # noqa: E402
from services.deco_service import (  # noqa: E402
    DecoService,
    WIFI_UPDATE_UNSUPPORTED_MESSAGE,
    WiFiUpdateNotSupportedError,
)

EXPECTED_MESSAGE = "WiFi changes aren't supported yet; change them in the Deco app"

UPDATE_CASES = [
    {"ssid": "NewNetwork"},
    {"password": "NewPassword123"},
    {"band_steering": True},
    {"ssid": "NewNetwork", "password": "NewPassword123", "band_steering": False},
]


def _assert_router_never_called(mock_client):
    assert mock_client.method_calls == []
    assert mock_client.mock_calls == []


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(router)
    original = deco_routes.deco_service
    yield app
    deco_routes.deco_service = original


def test_message_text():
    assert WIFI_UPDATE_UNSUPPORTED_MESSAGE == EXPECTED_MESSAGE


@pytest.mark.parametrize("kwargs", UPDATE_CASES)
def test_service_update_raises_not_supported_without_router_call(kwargs):
    mock_client = Mock()
    service = DecoService(deco_client=mock_client)
    mock_client.reset_mock()

    with pytest.raises(WiFiUpdateNotSupportedError) as exc_info:
        service.update_wifi_config(**kwargs)

    assert str(exc_info.value) == EXPECTED_MESSAGE
    _assert_router_never_called(mock_client)


def test_service_update_does_not_raise_attribute_error():
    # A spec'd client without update_wifi_settings used to cause AttributeError.
    mock_client = Mock(spec=["get_wifi_settings"])
    service = DecoService(deco_client=mock_client)

    with pytest.raises(WiFiUpdateNotSupportedError):
        service.update_wifi_config(ssid="NewNetwork")
    mock_client.get_wifi_settings.assert_not_called()


def test_service_update_keeps_cached_wifi_config():
    mock_client = Mock()
    service = DecoService(deco_client=mock_client)
    service._wifi_config_cache = {"ssid": "Current"}
    mock_client.reset_mock()

    with pytest.raises(WiFiUpdateNotSupportedError):
        service.update_wifi_config(ssid="NewNetwork")

    assert service._wifi_config_cache == {"ssid": "Current"}
    _assert_router_never_called(mock_client)


@pytest.mark.parametrize("body", UPDATE_CASES + [{}])
def test_put_wifi_config_returns_501_without_router_call(api_client, body):
    mock_client = Mock()
    deco_routes.deco_service = DecoService(deco_client=mock_client)
    mock_client.reset_mock()

    response = TestClient(api_client).put("/api/deco/wifi-config", json=body)

    assert response.status_code == 501
    assert response.json() == {"detail": EXPECTED_MESSAGE}
    _assert_router_never_called(mock_client)


def test_put_wifi_config_returns_501_when_service_not_initialized(api_client):
    deco_routes.deco_service = None

    response = TestClient(api_client).put("/api/deco/wifi-config", json={"ssid": "NewNetwork"})

    assert response.status_code == 501
    assert response.json() == {"detail": EXPECTED_MESSAGE}


def test_get_wifi_config_still_works(api_client):
    mock_client = Mock()
    mock_client.get_wifi_settings.return_value = {"ssid": "HomeNet", "band_steering": True}
    deco_routes.deco_service = DecoService(deco_client=mock_client)

    response = TestClient(api_client).get("/api/deco/wifi-config")

    assert response.status_code == 200
    mock_client.get_wifi_settings.assert_called_once()
