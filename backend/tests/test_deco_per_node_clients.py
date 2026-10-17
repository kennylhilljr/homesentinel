"""Per-node client reads for Deco firmware where the aggregate client_list fails.

Observed live on 2026-10-13: the BE63 nodes return HTTP 500 for device_mac="default"
but answer 60-74 clients when asked about their own MAC, and the master times out.
"""
import json
import secrets
import time

import pytest

from services import deco_client as dc
from services.deco_client import APIConnectionError, DecoClient

MASTER = "10-5A-95-3D-63-42"
X55 = "8C-90-2D-2D-9A-20"
BE63 = "10-5A-95-3D-62-E2"

NODES = [
    {"mac": MASTER, "role": "master", "device_model": "BE63",
     "wired_port_list": [{"mac": "AA-AA-AA-AA-AA-01"}]},
    {"mac": X55, "role": "slave", "device_model": "X55"},
    {"mac": BE63, "role": "slave", "device_model": "BE63"},
]
IPS = {MASTER: "192.168.12.97", X55: "192.168.12.226", BE63: "192.168.12.208"}

ONLINE_X55 = {"mac": "11-11-11-11-11-01", "online": True, "name": "RWNobw==", "ip": "192.168.12.31"}
ONLINE_BE63 = {"mac": "22-22-22-22-22-02", "online": True, "name": "", "ip": "192.168.12.32"}
OFFLINE_BE63 = {"mac": "22-22-22-22-22-03", "online": False, "name": "", "ip": "192.168.12.33"}


class FakeLocalClient:
    """Stands in for the temporary DecoClient sessions the real code opens."""

    client_lists = {}   # host -> list of clients, or an Exception to raise
    requests = []       # (host, device_mac) for every client_list read

    def __init__(self, local_endpoint=None, use_cloud=False, verify_ssl=False, **kwargs):
        self.local_endpoint = local_endpoint
        self.host = local_endpoint.split("//")[-1]

    def authenticate(self):
        return None

    def _local_encrypted_request(self, path, data):
        if "device_list" in path:
            return {"device_list": NODES}
        mac = json.loads(data)["params"]["device_mac"]
        FakeLocalClient.requests.append((self.host, mac))
        if mac == "default":
            raise APIConnectionError("Local API request failed: HTTP 500")
        entry = FakeLocalClient.client_lists[self.host]
        if isinstance(entry, Exception):
            raise entry
        return {"client_list": entry}

    def close(self):
        pass


@pytest.fixture
def deco(monkeypatch):
    monkeypatch.setattr(dc, "_topology_cache", None)
    monkeypatch.setattr(dc, "_topology_cache_time", None)
    monkeypatch.setattr(dc, "_client_list_broken", False)
    monkeypatch.setattr(dc, "_client_list_broken_time", None)
    monkeypatch.setattr(dc, "TOPOLOGY_CACHE_TTL", 0)
    dc._node_client_failed.clear()
    dc._per_node_clients.clear()
    FakeLocalClient.requests = []
    FakeLocalClient.client_lists = {
        IPS[X55]: [ONLINE_X55],
        IPS[BE63]: [ONLINE_BE63, OFFLINE_BE63],
        IPS[MASTER]: APIConnectionError("timeout"),
    }
    client = DecoClient(local_endpoint=f"http://{IPS[MASTER]}", use_cloud=False, verify_ssl=False)
    client.password = secrets.token_hex(8)  # throwaway value; the fake client never checks it
    client.set_node_endpoints(IPS)
    monkeypatch.setattr(dc, "DecoClient", FakeLocalClient)
    return client


def test_failed_aggregate_query_falls_back_to_each_node(deco):
    topology = deco.get_topology_local()

    clients = topology["node_clients"]
    assert [c["mac"] for c in clients[X55]] == [ONLINE_X55["mac"]]
    # BE63 lists offline history too; only clients online on that node count.
    assert [c["mac"] for c in clients[BE63]] == [ONLINE_BE63["mac"]]


def test_node_that_cannot_answer_keeps_wired_port_mapping(deco):
    topology = deco.get_topology_local()

    master_clients = topology["node_clients"][MASTER]
    assert [c["mac"] for c in master_clients] == ["AA-AA-AA-AA-AA-01"]


def test_failed_node_is_skipped_until_retry_interval(deco):
    deco.get_topology_local()
    deco.get_topology_local()

    reads = [host for host, mac in FakeLocalClient.requests if mac != "default"]
    assert reads.count(IPS[MASTER]) == 1          # failed once, then skipped
    assert reads.count(IPS[X55]) == 2             # healthy nodes are read each time


def test_node_is_retried_after_interval(deco):
    deco.get_topology_local()
    dc._node_client_failed[MASTER] = time.time() - dc._NODE_CLIENT_RETRY_INTERVAL - 1
    deco.get_topology_local()

    reads = [host for host, mac in FakeLocalClient.requests if mac != "default"]
    assert reads.count(IPS[MASTER]) == 2


def test_client_list_local_falls_back_to_flattened_node_clients(deco, monkeypatch):
    monkeypatch.setattr(dc, "_client_list_broken", True)
    monkeypatch.setattr(dc, "_client_list_broken_time", time.time())

    clients = deco.get_client_list_local()

    assert {c["mac"] for c in clients} == {ONLINE_X55["mac"], ONLINE_BE63["mac"]}
    assert next(c for c in clients if c["mac"] == ONLINE_X55["mac"])["name"] == "Echo"


def test_node_without_endpoint_is_not_queried(deco):
    deco.set_node_endpoints({X55: IPS[X55]})

    deco.get_topology_local()

    queried = {host for host, mac in FakeLocalClient.requests if mac != "default"}
    assert queried == {IPS[X55]}
