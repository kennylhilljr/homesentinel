import asyncio
import time
from types import SimpleNamespace

import pytest

from routes import deco


@pytest.fixture(autouse=True)
def reset_client_node_map_cache(monkeypatch):
    monkeypatch.setattr(deco, "_client_node_map_cache", None)
    monkeypatch.setattr(deco, "_client_node_map_cache_time", 0.0)
    monkeypatch.setattr(deco, "_client_node_map_refresh_task", None)
    monkeypatch.setattr(deco, "CLIENT_NODE_MAP_CACHE_TTL", 0)
    monkeypatch.setattr(deco, "CLIENT_NODE_MAP_TIMEOUT", 0.05)
    yield


def _service(fetch):
    return SimpleNamespace(
        deco_client=SimpleNamespace(get_topology_local=fetch),
        _device_repo=None,
    )


def _topology(client_mac="001122334455"):
    return {
        "nodes": [{"mac": "AA-BB-CC-DD-EE-FF", "nickname": "Office", "role": "master"}],
        "node_clients": {
            "AA-BB-CC-DD-EE-FF": [{"mac": client_mac, "connection_type": "band5"}],
        },
    }


def test_blocking_topology_fetch_does_not_block_event_loop(monkeypatch):
    def slow_fetch():
        time.sleep(0.04)
        return _topology()

    monkeypatch.setattr(deco, "deco_service", _service(slow_fetch))
    monkeypatch.setattr(deco, "CLIENT_NODE_MAP_TIMEOUT", 0.2)

    async def scenario():
        endpoint = asyncio.create_task(deco.get_client_node_map())
        started = asyncio.get_running_loop().time()
        await asyncio.sleep(0.01)
        elapsed = asyncio.get_running_loop().time() - started
        return elapsed, await endpoint

    elapsed, response = asyncio.run(scenario())

    assert elapsed < 0.03
    assert response["client_node_map"]["00:11:22:33:44:55"]["node_name"] == "Office"
    assert response["degraded"] is False
    assert response["stale"] is False


def test_refresh_that_finishes_after_the_timeout_is_cached_for_the_next_request(monkeypatch):
    # Real bug (2026-10-15): a refresh slower than the route timeout finished in the
    # background but was never stored, so the map stayed frozen on old data forever.
    calls = []

    def slow_fetch():
        calls.append(1)
        time.sleep(0.15)
        return _topology(client_mac="aabbccddeeff")

    monkeypatch.setattr(deco, "deco_service", _service(slow_fetch))
    monkeypatch.setattr(deco, "CLIENT_NODE_MAP_TIMEOUT", 0.05)
    monkeypatch.setattr(deco, "CLIENT_NODE_MAP_CACHE_TTL", 60)

    async def scenario():
        first = await deco.get_client_node_map()
        await asyncio.sleep(0.3)
        second = await deco.get_client_node_map()
        return first, second

    first, second = asyncio.run(scenario())

    assert first["degraded"] is True
    assert second["degraded"] is False
    assert second["cached"] is True
    assert "aa:bb:cc:dd:ee:ff" in second["client_node_map"]
    assert len(calls) == 1  # the finished refresh was reused, not restarted


def test_timeout_serves_last_known_data_with_degraded_metadata(monkeypatch):
    cached = {
        "client_node_map": {"00:11:22:33:44:55": {"node_name": "Office"}},
        "nodes": {"AA-BB-CC-DD-EE-FF": "Office"},
        "node_details": {},
        "total_mapped": 1,
    }
    monkeypatch.setattr(deco, "_client_node_map_cache", cached)
    monkeypatch.setattr(deco, "_client_node_map_cache_time", time.monotonic() - 120)

    calls = 0

    def stalled_fetch():
        nonlocal calls
        calls += 1
        time.sleep(0.15)
        return _topology("66778899aabb")

    monkeypatch.setattr(deco, "deco_service", _service(stalled_fetch))

    async def scenario():
        return await asyncio.gather(
            deco.get_client_node_map(),
            deco.get_client_node_map(),
        )

    first, second = asyncio.run(scenario())

    assert calls == 1
    assert first["client_node_map"] == cached["client_node_map"]
    assert second["client_node_map"] == cached["client_node_map"]
    assert first["degraded"] is True
    assert first["stale"] is True
    assert first["cached"] is True
    assert first["error"] == "Deco topology refresh timed out"


def test_timeout_without_cache_returns_compatible_empty_payload(monkeypatch):
    def stalled_fetch():
        time.sleep(0.15)
        return _topology()

    monkeypatch.setattr(deco, "deco_service", _service(stalled_fetch))

    response = asyncio.run(deco.get_client_node_map())

    assert response["client_node_map"] == {}
    assert response["nodes"] == {}
    assert response["node_details"] == {}
    assert response["total_mapped"] == 0
    assert response["degraded"] is True
    assert response["stale"] is False
    assert response["cached"] is False
