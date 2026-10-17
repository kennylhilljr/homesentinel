"""
Authoritative LAN view taken from the Chester router.

The Chester is the DHCP server and gateway, so its neighbor table, lease file
and host reservations are the most reliable record of which MAC holds which IP
and whether it is on the network. Reading them over SSH avoids depending on the
Mac's own ARP cache, which can come back empty.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Neighbor states that mean the router has recently heard from the device.
ONLINE_STATES = frozenset({"REACHABLE", "DELAY", "PROBE"})

# A STALE entry is only trusted if the device was confirmed this recently.
DEFAULT_MAX_STALE_AGE = 120

# Probe every STALE entry first so a live device turns REACHABLE and a gone one
# does not linger as STALE for hours, then dump the three tables.
SNAPSHOT_COMMAND = r"""
for ip in $(ip -4 neigh show dev br-lan | awk '$NF=="STALE"{print $1}'); do
  ip neigh change $ip dev br-lan nud probe 2>/dev/null
done
sleep 4
echo '##NEIGH'; ip -4 -s neigh show dev br-lan
echo '##LEASES'; cat /tmp/dhcp.leases 2>/dev/null
echo '##RESERVATIONS'; uci show dhcp 2>/dev/null | grep -E '=host$|\.(name|mac|ip)='
"""

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_NEIGH_RE = re.compile(r"^(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?:dev\s+\S+\s+)?lladdr\s+(?P<mac>\S+)(?P<rest>.*)$")
_USED_RE = re.compile(r"used\s+(\d+)/(\d+)/(\d+)")
_UCI_RE = re.compile(r"^dhcp\.@host\[(\d+)\]\.(name|mac|ip)='(.*)'$")


@dataclass(frozen=True)
class Neighbor:
    mac: str
    ip: str
    state: str
    confirmed_age: Optional[int] = None  # seconds since the router last confirmed it


@dataclass(frozen=True)
class Lease:
    mac: str
    ip: str
    hostname: Optional[str]
    expiry: int  # epoch seconds, 0 means infinite


@dataclass(frozen=True)
class Reservation:
    mac: str
    ip: str
    name: str = ""


@dataclass
class NetworkSnapshot:
    neighbors: List[Neighbor] = field(default_factory=list)
    leases: List[Lease] = field(default_factory=list)
    reservations: List[Reservation] = field(default_factory=list)

    def online_neighbors(self, max_stale_age: int = DEFAULT_MAX_STALE_AGE) -> Dict[str, Neighbor]:
        """MAC -> Neighbor for devices the router currently considers present."""
        online: Dict[str, Neighbor] = {}
        for n in self.neighbors:
            alive = n.state in ONLINE_STATES or (
                n.state == "STALE" and n.confirmed_age is not None and n.confirmed_age <= max_stale_age
            )
            if not alive:
                continue
            best = online.get(n.mac)
            if best is None or (n.confirmed_age or 0) < (best.confirmed_age or 0):
                online[n.mac] = n
        return online

    def ip_hints(self) -> Dict[str, str]:
        """MAC -> IP the router has assigned or reserved. Reservations win over leases."""
        now = time.time()
        hints = {l.mac: l.ip for l in self.leases if l.expiry == 0 or l.expiry > now}
        hints.update({r.mac: r.ip for r in self.reservations})
        return hints


def parse_ip_neigh(text: str) -> List[Neighbor]:
    """Parse `ip -s neigh` output. Rows without a lladdr (FAILED, INCOMPLETE) are skipped."""
    neighbors = []
    for line in text.splitlines():
        m = _NEIGH_RE.match(line.strip())
        if not m:
            continue
        mac = m.group("mac").lower()
        if not _MAC_RE.match(mac):
            continue
        rest = m.group("rest").split()
        state = rest[-1] if rest else ""
        used = _USED_RE.search(m.group("rest"))
        neighbors.append(
            Neighbor(
                mac=mac,
                ip=m.group("ip"),
                state=state,
                confirmed_age=int(used.group(2)) if used else None,
            )
        )
    return neighbors


def parse_dhcp_leases(text: str) -> List[Lease]:
    """Parse dnsmasq `dhcp.leases`: `expiry mac ip hostname clientid`."""
    leases = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        mac = parts[1].lower()
        if not _MAC_RE.match(mac) or not _IPV4_RE.match(parts[2]):
            continue
        hostname = None if parts[3] == "*" else parts[3]
        leases.append(Lease(mac=mac, ip=parts[2], hostname=hostname, expiry=int(parts[0])))
    return leases


def parse_uci_hosts(text: str) -> List[Reservation]:
    """Parse `uci show dhcp` host sections into reservations."""
    sections: Dict[str, Dict[str, str]] = {}
    for line in text.splitlines():
        m = _UCI_RE.match(line.strip())
        if m:
            sections.setdefault(m.group(1), {})[m.group(2)] = m.group(3)

    reservations = []
    for fields in sections.values():
        mac = fields.get("mac", "").lower()
        ip = fields.get("ip", "")
        if _MAC_RE.match(mac) and _IPV4_RE.match(ip):
            reservations.append(Reservation(mac=mac, ip=ip, name=fields.get("name", "")))
    return reservations


def parse_snapshot_output(output: str) -> NetworkSnapshot:
    """Split the marked output of SNAPSHOT_COMMAND into a NetworkSnapshot."""
    sections: Dict[str, List[str]] = {}
    current = None
    for line in output.splitlines():
        if line.startswith("##"):
            current = line[2:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)

    def body(name: str) -> str:
        return "\n".join(sections.get(name, []))

    return NetworkSnapshot(
        neighbors=parse_ip_neigh(body("NEIGH")),
        leases=parse_dhcp_leases(body("LEASES")),
        reservations=parse_uci_hosts(body("RESERVATIONS")),
    )


class ChesterNetworkSource:
    """Takes a NetworkSnapshot by running SNAPSHOT_COMMAND through `runner`.

    `runner` is a callable that executes a shell command on the Chester and
    returns its stdout. Any exception it raises propagates to the caller.
    """

    def __init__(self, runner: Callable[[str], str], command: str = SNAPSHOT_COMMAND):
        self._runner = runner
        self._command = command

    def snapshot(self) -> NetworkSnapshot:
        snap = parse_snapshot_output(self._runner(self._command))
        logger.info(
            f"Chester snapshot: {len(snap.neighbors)} neighbors, "
            f"{len(snap.leases)} leases, {len(snap.reservations)} reservations"
        )
        return snap
