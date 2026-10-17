"""Tests for the Chester-backed network source and its use in scan_and_update.

Regression coverage for real failures seen on 2026-10-12:
  * Deco node IPs in the DB were stale although the Chester held reservations.
  * With the Mac's `arp -a` returning nothing, every device was marked offline.
  * A failed local Deco login silently fell back to the TP-Link cloud, which
    locked the account.
"""
import logging
import os
import secrets
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from db import Database
from services.chester_network import (
    ChesterNetworkSource,
    NetworkSnapshot,
    Neighbor,
    Reservation,
    parse_dhcp_leases,
    parse_ip_neigh,
    parse_snapshot_output,
    parse_uci_hosts,
)
from services.deco_client import APIConnectionError, DecoClient
from services.device_scanner import ARPScanner, DeviceInfo, NetworkDeviceService

NEIGH_TEXT = """\
192.168.12.194 dev br-lan lladdr b8:3a:9d:62:2e:15 used 79/79/52 probes 1 STALE
192.168.12.84 dev br-lan  used 43611/45266/43608 probes 6 FAILED
192.168.12.124 dev br-lan lladdr a4:7e:fa:42:c6:c0 used 79461/79461/79414 probes 1 STALE
192.168.12.58 dev br-lan lladdr ba:3a:9d:ad:88:bc ref 1 used 0/0/0 probes 1 REACHABLE
192.168.12.77 dev br-lan lladdr 02:00:00:00:00:77 used 3/3/1 probes 0 DELAY
"""

LEASES_TEXT = """\
1791891821 8c:90:2d:2d:9a:20 192.168.12.226 Deco-Garage 01:8c:90:2d:2d:9a:20
1791891822 aa:bb:cc:dd:ee:ff 192.168.12.50 * *
"""

UCI_TEXT = """\
dhcp.@host[0]=host
dhcp.@host[0].name='Deco-Office'
dhcp.@host[0].mac='10:5A:95:3D:63:42'
dhcp.@host[0].ip='192.168.12.97'
dhcp.@host[0].leasetime='infinite'
dhcp.@host[1]=host
dhcp.@host[1].name='Deco-Garage'
dhcp.@host[1].mac='8C:90:2D:2D:9A:20'
dhcp.@host[1].ip='192.168.12.226'
"""


# ── parsers ──────────────────────────────────────────────────────────────────

def test_parse_ip_neigh_skips_entries_without_lladdr():
    neighbors = {n.mac: n for n in parse_ip_neigh(NEIGH_TEXT)}
    assert "b8:3a:9d:62:2e:15" in neighbors
    assert len(neighbors) == 4  # the FAILED row has no MAC
    assert neighbors["b8:3a:9d:62:2e:15"].state == "STALE"
    assert neighbors["b8:3a:9d:62:2e:15"].confirmed_age == 79
    assert neighbors["ba:3a:9d:ad:88:bc"].confirmed_age == 0


def test_parse_ip_neigh_accepts_output_filtered_by_dev():
    # `ip -4 -s neigh show dev br-lan` omits the "dev br-lan" column (seen on the live router).
    text = (
        "192.168.12.194 lladdr b8:3a:9d:62:2e:15 ref 1 used 17/17/17 probes 1 REACHABLE\n"
        "192.168.12.84  used 44249/45904/44246 probes 6 FAILED\n"
    )
    neighbors = parse_ip_neigh(text)
    assert [(n.ip, n.mac, n.state, n.confirmed_age) for n in neighbors] == [
        ("192.168.12.194", "b8:3a:9d:62:2e:15", "REACHABLE", 17)
    ]


def test_online_rule_uses_state_and_age():
    snap = NetworkSnapshot(neighbors=parse_ip_neigh(NEIGH_TEXT))
    online = snap.online_neighbors(max_stale_age=120)
    assert "ba:3a:9d:ad:88:bc" in online          # REACHABLE
    assert "02:00:00:00:00:77" in online          # DELAY
    assert "b8:3a:9d:62:2e:15" in online          # STALE but confirmed 79s ago
    assert "a4:7e:fa:42:c6:c0" not in online      # STALE for 22 hours


def test_parse_dhcp_leases_handles_missing_hostname():
    leases = {l.mac: l for l in parse_dhcp_leases(LEASES_TEXT)}
    assert leases["8c:90:2d:2d:9a:20"].ip == "192.168.12.226"
    assert leases["8c:90:2d:2d:9a:20"].hostname == "Deco-Garage"
    assert leases["aa:bb:cc:dd:ee:ff"].hostname is None


def test_parse_uci_hosts_lowercases_macs():
    res = {r.mac: r for r in parse_uci_hosts(UCI_TEXT)}
    assert res["10:5a:95:3d:63:42"].ip == "192.168.12.97"
    assert res["8c:90:2d:2d:9a:20"].name == "Deco-Garage"


def test_snapshot_source_parses_marked_sections():
    output = f"##NEIGH\n{NEIGH_TEXT}##LEASES\n{LEASES_TEXT}##RESERVATIONS\n{UCI_TEXT}"
    snap = ChesterNetworkSource(runner=lambda cmd: output).snapshot()
    assert len(snap.neighbors) == 4
    assert len(snap.leases) == 2
    assert len(snap.reservations) == 2
    assert parse_snapshot_output(output).reservations == snap.reservations


def test_snapshot_source_propagates_runner_failure():
    def boom(cmd):
        raise OSError("ssh down")

    with pytest.raises(OSError):
        ChesterNetworkSource(runner=boom).snapshot()


# ── scan_and_update with a Chester source ────────────────────────────────────

SUBNET = "192.168.1.0/24"
DECO_MAC = "10:5a:95:3d:62:c4"


@pytest.fixture
def service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    db = Database(path)
    db.run_migrations()
    svc = NetworkDeviceService(db)
    svc.arp_scanner = MagicMock()
    svc.arp_scanner.scan_subnet.return_value = []
    svc.dhcp_parser = MagicMock()
    svc.dhcp_parser.parse_dhcp_leases.return_value = []
    yield svc
    db.close()
    os.unlink(path)


def _source(neighbors=(), reservations=(), error=None):
    src = MagicMock()
    if error:
        src.snapshot.side_effect = error
    else:
        src.snapshot.return_value = NetworkSnapshot(
            neighbors=list(neighbors), reservations=list(reservations)
        )
    return src


def _reachable(mac, ip):
    return Neighbor(mac=mac, ip=ip, state="REACHABLE", confirmed_age=0)


def test_stale_ip_is_corrected_from_chester(service):
    service.create_or_update_device(DECO_MAC, "192.168.1.127")
    service.set_network_source(_source([_reachable(DECO_MAC, "192.168.1.178")]))

    service.scan_and_update(SUBNET)

    dev = service.get_device_by_mac(DECO_MAC)
    assert dev["current_ip"] == "192.168.1.178"
    assert dev["status"] == "online"
    assert "192.168.1.127" in dev["ip_history"]


def test_devices_missing_from_chester_go_offline(service):
    service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.10")
    service.create_or_update_device("aa:bb:cc:dd:ee:02", "192.168.1.11")
    service.set_network_source(_source([_reachable("aa:bb:cc:dd:ee:01", "192.168.1.10")]))

    result = service.scan_and_update(SUBNET)

    assert result["devices_offline"] == 1
    assert service.get_device_by_mac("aa:bb:cc:dd:ee:02")["status"] == "offline"


def test_new_device_seen_only_by_chester_is_added(service):
    service.set_network_source(_source([_reachable("aa:bb:cc:dd:ee:09", "192.168.1.90")]))

    result = service.scan_and_update(SUBNET)

    assert result["devices_added"] == 1
    assert service.get_device_by_mac("aa:bb:cc:dd:ee:09")["current_ip"] == "192.168.1.90"


def test_local_arp_entry_not_confirmed_by_chester_is_not_online(service):
    service.arp_scanner.scan_subnet.return_value = [DeviceInfo("aa:bb:cc:dd:ee:33", "192.168.1.33")]
    service.set_network_source(_source([_reachable("aa:bb:cc:dd:ee:01", "192.168.1.10")]))

    service.scan_and_update(SUBNET)

    ghost = service.get_device_by_mac("aa:bb:cc:dd:ee:33")
    assert ghost is None or ghost["status"] != "online"


def test_total_data_loss_does_not_mark_everything_offline(service):
    service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.10")
    service.set_network_source(_source(error=OSError("ssh down")))

    result = service.scan_and_update(SUBNET)

    assert result["devices_offline"] == 0
    assert "warning" in result
    assert service.get_device_by_mac("aa:bb:cc:dd:ee:01")["status"] == "online"


def test_offline_device_ip_is_corrected_from_reservation(service):
    dev = service.create_or_update_device(DECO_MAC, "192.168.1.127")
    service.mark_offline(dev["device_id"])
    service.set_network_source(
        _source(
            [_reachable("aa:bb:cc:dd:ee:01", "192.168.1.10")],
            [Reservation(mac=DECO_MAC, ip="192.168.1.178", name="Deco-Living-Room")],
        )
    )

    service.scan_and_update(SUBNET)

    after = service.get_device_by_mac(DECO_MAC)
    assert after["current_ip"] == "192.168.1.178"
    assert after["status"] == "offline"


def test_reservations_sync_static_flags_both_ways(service):
    service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.10")
    service.create_or_update_device("aa:bb:cc:dd:ee:02", "192.168.1.11")
    service.device_repo.set_static_ip_reservation("aa:bb:cc:dd:ee:02", True, "192.168.1.11")
    service.set_network_source(
        _source(
            [_reachable("aa:bb:cc:dd:ee:01", "192.168.1.10"),
             _reachable("aa:bb:cc:dd:ee:02", "192.168.1.11")],
            [Reservation(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.10", name="one")],
        )
    )

    service.scan_and_update(SUBNET)

    one = service.get_device_by_mac("aa:bb:cc:dd:ee:01")
    two = service.get_device_by_mac("aa:bb:cc:dd:ee:02")
    assert one["static_ip_enabled"] == 1 and one["reserved_ip"] == "192.168.1.10"
    assert two["static_ip_enabled"] == 0 and two["reserved_ip"] is None


def test_empty_reservation_list_never_clears_static_flags(service):
    service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.10")
    service.device_repo.set_static_ip_reservation("aa:bb:cc:dd:ee:01", True, "192.168.1.10")
    service.set_network_source(_source([_reachable("aa:bb:cc:dd:ee:01", "192.168.1.10")], []))

    service.scan_and_update(SUBNET)

    assert service.get_device_by_mac("aa:bb:cc:dd:ee:01")["static_ip_enabled"] == 1


def test_deco_endpoint_follows_master_mac(service):
    deco = SimpleNamespace(
        local_endpoint="http://192.168.1.97",
        get_client_list_local=lambda: [],
        get_topology_local=lambda: {"nodes": [], "node_clients": {}},
    )
    service._deco_client = deco
    service._deco_master_mac = "aa:bb:cc:dd:ee:01"
    service._persist_deco_endpoint = MagicMock()
    service.set_network_source(_source([_reachable("aa:bb:cc:dd:ee:01", "192.168.1.226")]))

    service.scan_and_update(SUBNET)

    assert deco.local_endpoint == "http://192.168.1.226"
    service._persist_deco_endpoint.assert_called_once_with("http://192.168.1.226")


def test_deco_endpoint_untouched_when_master_has_not_moved(service):
    deco = SimpleNamespace(
        local_endpoint="http://192.168.1.97",
        get_client_list_local=lambda: [],
        get_topology_local=lambda: {"nodes": [], "node_clients": {}},
    )
    service._deco_client = deco
    service._deco_master_mac = "aa:bb:cc:dd:ee:01"
    service._persist_deco_endpoint = MagicMock()
    service.set_network_source(_source([_reachable("aa:bb:cc:dd:ee:01", "192.168.1.97")]))

    service.scan_and_update(SUBNET)

    assert deco.local_endpoint == "http://192.168.1.97"
    service._persist_deco_endpoint.assert_not_called()


def test_scan_pushes_node_endpoints_to_deco_client(service):
    deco = MagicMock()
    deco.local_endpoint = "http://192.168.1.97"
    deco.get_client_list_local.return_value = []
    deco.get_topology_local.return_value = {"nodes": [], "node_clients": {}}
    service._deco_client = deco
    service._deco_node_macs_cache = {"aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02", "aa:bb:cc:dd:ee:03"}
    service.set_network_source(
        _source(
            [_reachable("aa:bb:cc:dd:ee:01", "192.168.1.226")],
            [Reservation(mac="aa:bb:cc:dd:ee:02", ip="192.168.1.85", name="Deco-Back-Building")],
        )
    )

    service.scan_and_update(SUBNET)

    # Nodes the router knows nothing about (…:03) are left out.
    deco.set_node_endpoints.assert_called_with(
        {"aa:bb:cc:dd:ee:01": "192.168.1.226", "aa:bb:cc:dd:ee:02": "192.168.1.85"}
    )


# ── Deco cloud fallback (account lockout) ────────────────────────────────────

def test_local_mode_login_failure_never_calls_cloud():
    client = DecoClient(local_endpoint="http://192.168.1.97", use_cloud=False, verify_ssl=False)
    client.username, client.password = "admin", secrets.token_hex(8)  # throwaway value
    client._authenticate_local = MagicMock(side_effect=RuntimeError("timeout"))
    client._authenticate_cloud = MagicMock()

    with pytest.raises(APIConnectionError):
        client.authenticate()

    client._authenticate_cloud.assert_not_called()


# ── silent empty ARP read ────────────────────────────────────────────────────

def test_empty_arp_output_is_logged_as_warning(monkeypatch, caplog):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="", stderr=""),
    )
    with caplog.at_level(logging.WARNING, logger="services.device_scanner"):
        ARPScanner()._read_arp_table()
    assert any("empty" in r.message.lower() for r in caplog.records)
