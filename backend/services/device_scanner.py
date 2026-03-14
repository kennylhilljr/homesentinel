"""
Device Scanner Service for HomeSentinel
Implements ARP scanning, DHCP parsing, and device management
"""

import subprocess
import re
import logging
import os
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Information about a discovered device"""
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    vendor: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'hostname': self.hostname,
            'vendor': self.vendor
        }


@dataclass
class DHCPLease:
    """DHCP lease information"""
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    lease_start: Optional[datetime] = None
    lease_end: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'hostname': self.hostname,
            'lease_start': self.lease_start,
            'lease_end': self.lease_end
        }


class ARPScanner:
    """ARP Scanner for device discovery"""

    # Common vendor prefixes (partial list)
    VENDOR_MAP = {
        '00:00:00': 'XEROX',
        '00:00:0C': 'CISCO',
        '00:50:F2': 'MICROSOFT',
        '00:1A:A0': 'APPLE',
        'B8:27:EB': 'RASPBERRY PI',
        'DC:A6:32': 'RASPBERRY PI',
        'E4:5F:01': 'RASPBERRY PI',
        '08:00:27': 'VIRTUALBOX',
        '52:54:00': 'QEMU',
        '00:0C:29': 'VMWARE',
    }

    def __init__(self):
        self.has_arp_scan = self._check_arp_scan()
        self.has_nmap = self._check_nmap()
        logger.info(f"ARP Scanner initialized - arp-scan: {self.has_arp_scan}, nmap: {self.has_nmap}")

    def _check_arp_scan(self) -> bool:
        """Check if arp-scan is available"""
        try:
            result = subprocess.run(['which', 'arp-scan'], capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception:
            return False

    def _check_nmap(self) -> bool:
        """Check if nmap is available"""
        try:
            result = subprocess.run(['which', 'nmap'], capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception:
            return False

    def _get_vendor(self, mac_address: str) -> Optional[str]:
        """Get vendor name from MAC address prefix"""
        prefix = mac_address[:8].upper()
        for mac_prefix, vendor in self.VENDOR_MAP.items():
            if prefix.startswith(mac_prefix):
                return vendor
        return None

    def scan_subnet_with_arp_scan(self, subnet: str) -> List[DeviceInfo]:
        """Scan subnet using arp-scan"""
        devices = []
        try:
            # Try without sudo first (works if BPF permissions are set),
            # fall back to sudo (works if NOPASSWD sudo is configured).
            # -l = scan local network, --interface selects the right adapter.
            cmd = ['arp-scan', '-l']
            result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
            if result.returncode != 0 and 'Permission denied' in (result.stderr or ''):
                cmd = ['sudo', '-n', 'arp-scan', '-l']
                result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)

            if result.returncode != 0:
                logger.warning(f"arp-scan failed: {result.stderr}")
                return devices

            # Parse arp-scan output
            # Format: IP\tMAC\tVendor
            for line in result.stdout.split('\n'):
                if not line.strip() or line.startswith('Interface'):
                    continue

                parts = line.split('\t')
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    mac = parts[1].strip().lower()

                    # Skip incomplete entries
                    if not ip or not mac or ip.startswith('---'):
                        continue

                    vendor = parts[2].strip() if len(parts) > 2 else self._get_vendor(mac)
                    device = DeviceInfo(
                        mac_address=mac,
                        ip_address=ip,
                        vendor=vendor
                    )
                    devices.append(device)
                    logger.debug(f"Discovered device: {ip} ({mac})")

        except subprocess.TimeoutExpired:
            logger.error("arp-scan timed out")
        except Exception as e:
            logger.error(f"Error scanning with arp-scan: {e}")

        return devices

    def _read_arp_table(self) -> Dict[str, str]:
        """Read the system ARP table to map IP -> MAC address"""
        arp_map = {}
        try:
            result = subprocess.run(['arp', '-a'], capture_output=True, timeout=10, text=True)
            if result.returncode != 0:
                logger.warning(f"arp -a failed: {result.stderr}")
                return arp_map

            for line in result.stdout.split('\n'):
                # macOS format: ? (192.168.12.1) at 58:48:49:61:39:72 on en0 ...
                # Linux format:  ? (192.168.12.1) at 58:48:49:61:39:72 [ether] on eth0
                match = re.search(r'\(([\d.]+)\)\s+at\s+([\da-fA-F:]+)', line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2).lower()
                    # Skip incomplete, broadcast, and multicast
                    if mac != '(incomplete)' and mac != 'ff:ff:ff:ff:ff:ff':
                        # Normalize MAC to always use 2-digit hex octets
                        parts = mac.split(':')
                        mac = ':'.join(p.zfill(2) for p in parts)
                        arp_map[ip] = mac

        except Exception as e:
            logger.error(f"Error reading ARP table: {e}")

        return arp_map

    def scan_subnet_with_nmap(self, subnet: str) -> List[DeviceInfo]:
        """Scan subnet using nmap, then resolve MACs from ARP table"""
        devices = []
        try:
            # Use nmap -sn for ping scan (triggers ARP resolution)
            cmd = ['nmap', '-sn', subnet, '-oG', '-']
            result = subprocess.run(cmd, capture_output=True, timeout=120, text=True)

            if result.returncode != 0 and result.returncode != 1:
                logger.warning(f"nmap scan had issues: {result.stderr}")

            # Collect discovered IPs and hostnames
            discovered = []
            for line in result.stdout.split('\n'):
                if line.startswith('Host:'):
                    match = re.search(r'Host:\s+([\d.]+)', line)
                    if match:
                        ip = match.group(1)
                        hostname_match = re.search(r'\((.*?)\)', line)
                        hostname = hostname_match.group(1) if hostname_match else None
                        discovered.append((ip, hostname))

            # Now read the ARP table to get real MAC addresses
            arp_map = self._read_arp_table()

            for ip, hostname in discovered:
                mac = arp_map.get(ip)
                if not mac:
                    logger.debug(f"No MAC in ARP table for {ip}, skipping")
                    continue

                vendor = self._get_vendor(mac)
                device = DeviceInfo(
                    mac_address=mac,
                    ip_address=ip,
                    hostname=hostname,
                    vendor=vendor
                )
                devices.append(device)
                logger.debug(f"Discovered device: {ip} ({mac})")

        except subprocess.TimeoutExpired:
            logger.error("nmap scan timed out")
        except Exception as e:
            logger.error(f"Error scanning with nmap: {e}")

        return devices

    def scan_arp_table_only(self) -> List[DeviceInfo]:
        """Scan using just the ARP table (no nmap/arp-scan needed)"""
        devices = []
        arp_map = self._read_arp_table()

        for ip, mac in arp_map.items():
            vendor = self._get_vendor(mac)
            device = DeviceInfo(
                mac_address=mac,
                ip_address=ip,
                vendor=vendor
            )
            devices.append(device)
            logger.debug(f"ARP table device: {ip} ({mac})")

        return devices

    def scan_subnet(self, subnet: str) -> List[DeviceInfo]:
        """Scan a subnet for devices (/24 CIDR notation).

        # 2026-03-09: Changed to always merge ARP table entries into scan results.
        # Previously ARP table was fallback-only (only when nmap found zero devices).
        # nmap ping scan misses many IoT devices that don't respond to ICMP/TCP probes,
        # but those devices still appear in the ARP table from recent L2 traffic.
        """
        logger.info(f"Starting subnet scan: {subnet}")

        # Validate subnet format
        if not self._validate_subnet(subnet):
            logger.error(f"Invalid subnet format: {subnet}")
            return []

        devices = []

        # Try arp-scan first, then nmap, then ARP table alone
        if self.has_arp_scan:
            devices = self.scan_subnet_with_arp_scan(subnet)
        elif self.has_nmap:
            devices = self.scan_subnet_with_nmap(subnet)

        # Always supplement with ARP table entries (catches devices that didn't
        # respond to nmap probes but have recent ARP cache entries from L2 traffic)
        seen_macs = {d.mac_address for d in devices}
        arp_devices = self.scan_arp_table_only()
        added_from_arp = 0
        for arp_dev in arp_devices:
            if arp_dev.mac_address not in seen_macs:
                devices.append(arp_dev)
                seen_macs.add(arp_dev.mac_address)
                added_from_arp += 1

        if added_from_arp:
            logger.info(f"ARP table supplement added {added_from_arp} devices not found by scan")

        logger.info(f"Scan completed, found {len(devices)} devices")
        return devices

    def _validate_subnet(self, subnet: str) -> bool:
        """Validate subnet format (e.g., 192.168.1.0/24)"""
        # For simplicity, accept CIDR or interface name
        if '/' in subnet:
            # CIDR notation
            parts = subnet.split('/')
            if len(parts) != 2:
                return False
            try:
                int(parts[1])
                return True
            except ValueError:
                return False
        else:
            # Assume it's an interface or direct IP
            return True


class DHCPParser:
    """DHCP Lease Parser"""

    DHCP_PATHS = {
        'linux': '/var/lib/dhcp/dhcpd.leases',
        'darwin': '/var/db/dhcpd_leases',
        'win32': 'C:\\ProgramData\\ISC DHCP\\dhcpd.leases'
    }

    def __init__(self):
        self.dhcp_path = self._find_dhcp_file()
        if self.dhcp_path:
            logger.info(f"Found DHCP lease file: {self.dhcp_path}")
        else:
            logger.warning("DHCP lease file not found")

    def _find_dhcp_file(self) -> Optional[str]:
        """Find DHCP lease file for current OS"""
        import sys
        import platform

        # Try OS-specific paths
        if sys.platform.startswith('linux'):
            paths = [
                '/var/lib/dhcp/dhcpd.leases',
                '/var/lib/isc-dhcp-server/dhcpd.leases',
                '/var/lib/dhcpd/dhcpd.leases',
            ]
        elif sys.platform == 'darwin':
            paths = ['/var/db/dhcpd_leases']
        elif sys.platform == 'win32':
            paths = ['C:\\ProgramData\\ISC DHCP\\dhcpd.leases']
        else:
            paths = []

        for path in paths:
            if os.path.exists(path):
                return path

        return None

    def parse_leases(self) -> List[DHCPLease]:
        """Parse DHCP lease file"""
        leases = []

        if not self.dhcp_path or not os.path.exists(self.dhcp_path):
            logger.warning("DHCP lease file not accessible")
            return leases

        try:
            with open(self.dhcp_path, 'r') as f:
                content = f.read()

            # Parse lease entries
            # Format varies by DHCP server, but typically:
            # lease 192.168.1.100 { hardware ethernet aa:bb:cc:dd:ee:ff; ... }

            lease_pattern = r'lease\s+([\d.]+)\s*\{([^}]*)\}'
            for match in re.finditer(lease_pattern, content):
                ip = match.group(1)
                lease_block = match.group(2)

                # Extract MAC address
                mac_match = re.search(r'hardware\s+ethernet\s+([\da-f:]+)', lease_block)
                mac = mac_match.group(1).lower() if mac_match else None

                if not mac:
                    continue

                # Extract hostname if present
                hostname_match = re.search(r'client-hostname\s+"([^"]+)"', lease_block)
                hostname = hostname_match.group(1) if hostname_match else None

                # Extract dates
                starts_match = re.search(r'starts\s+\d+\s+([\d/:]+)', lease_block)
                ends_match = re.search(r'ends\s+\d+\s+([\d/:]+)', lease_block)

                lease = DHCPLease(
                    mac_address=mac,
                    ip_address=ip,
                    hostname=hostname,
                    lease_start=starts_match.group(1) if starts_match else None,
                    lease_end=ends_match.group(1) if ends_match else None
                )
                leases.append(lease)
                logger.debug(f"Parsed lease: {ip} ({mac})")

        except PermissionError:
            logger.warning(f"Permission denied reading DHCP file: {self.dhcp_path}")
        except Exception as e:
            logger.error(f"Error parsing DHCP leases: {e}")

        return leases


class NetworkDeviceService:
    """Service for managing network devices"""

    def __init__(self, db):
        self.db = db
        from db import NetworkDeviceRepository, PollingConfigRepository
        from services.oui_service import OUIService
        self.device_repo = NetworkDeviceRepository(db)
        self.config_repo = PollingConfigRepository(db)
        self.oui_service = OUIService()
        self.arp_scanner = ARPScanner()
        self.dhcp_parser = DHCPParser()
        self._deco_client = None  # Set via set_deco_client() for Deco online status
        self._event_service = None  # Set via set_event_service() for event creation

    def set_deco_client(self, deco_client):
        """Set the Deco client for supplementary online status detection.
        # 2026-03-09: The Deco router is the DHCP server/gateway, so it has the
        # most complete view of connected devices. We use its client list to
        # supplement the ARP scan — if either source says a device is on, it's on.
        """
        self._deco_client = deco_client

    def set_event_service(self, event_service):
        """Set the event service for recording device state transitions.
        2026-03-14: Enables event and alert creation when devices come online/offline.
        """
        self._event_service = event_service

    def create_or_update_device(self, mac_address: str, ip_address: Optional[str] = None) -> dict:
        """Create or update a network device"""
        # Generate device ID from MAC address
        device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac_address))

        return self.device_repo.create_or_update(device_id, mac_address, ip_address)

    def _record_device_event(self, device_id: str, event_type: str, description: str = None):
        """Record a device event if event service is available.
        2026-03-14: Creates events and alerts for device state transitions.
        """
        if not self._event_service:
            return

        try:
            # Record the event
            event_id = self._event_service.record_event(
                device_id=device_id,
                event_type=event_type,
                description=description
            )

            # Create alert for certain event types
            if event_type == 'new_device':
                alert_type = 'new_device'
                self._event_service.create_alert(
                    device_id=device_id,
                    event_id=event_id,
                    alert_type=alert_type
                )
                logger.info(f"New device alert created: {device_id}")
            elif event_type == 'disconnected':
                alert_type = 'device_offline'
                self._event_service.create_alert(
                    device_id=device_id,
                    event_id=event_id,
                    alert_type=alert_type
                )
                logger.info(f"Device offline alert created: {device_id}")

        except Exception as e:
            logger.warning(f"Failed to record device event: {e}")

    def get_device(self, device_id: str) -> Optional[dict]:
        """Get device by ID"""
        return self.device_repo.get_by_id(device_id)

    def get_device_by_mac(self, mac_address: str) -> Optional[dict]:
        """Get device by MAC address"""
        return self.device_repo.get_by_mac(mac_address)

    def list_devices(self) -> List[dict]:
        """List all devices"""
        return self.device_repo.list_all()

    def list_online_devices(self) -> List[dict]:
        """List online devices"""
        return self.device_repo.list_by_status('online')

    def list_offline_devices(self) -> List[dict]:
        """List offline devices"""
        return self.device_repo.list_by_status('offline')

    def mark_offline(self, device_id: str) -> Optional[dict]:
        """Mark device as offline"""
        return self.device_repo.mark_offline(device_id)

    def mark_online(self, device_id: str) -> Optional[dict]:
        """Mark device as online"""
        return self.device_repo.mark_online(device_id)

    def scan_and_update(self, subnet: str) -> dict:
        """Scan subnet and update device database.

        # 2026-03-09: Now merges Deco client list as supplementary online source.
        # If either ARP scan or Deco says a device is online, it's online.
        # This fixes the issue where nmap ping scan only finds ~12 responsive hosts
        # while Deco (as DHCP server/gateway) sees 58+ connected clients.
        """
        start_time = datetime.utcnow()
        scan_results = {
            'devices_found': 0,
            'devices_added': 0,
            'devices_updated': 0,
            'devices_offline': 0,
            'deco_online': 0,
            'timestamp': start_time.isoformat(),
            'scan_time_seconds': 0
        }

        try:
            # Scan for devices via ARP/nmap
            discovered_devices = self.arp_scanner.scan_subnet(subnet)
            scan_results['devices_found'] = len(discovered_devices)

            # Track which MACs are currently online
            online_macs = set()

            # Update database with discovered devices
            for device_info in discovered_devices:
                existing = self.get_device_by_mac(device_info.mac_address)
                if existing:
                    # Update existing device
                    self.create_or_update_device(device_info.mac_address, device_info.ip_address)
                    scan_results['devices_updated'] += 1
                else:
                    # Create new device with vendor lookup
                    device = self.create_or_update_device(device_info.mac_address, device_info.ip_address)
                    # Auto-populate vendor from OUI database
                    vendor = device_info.vendor or self.oui_service.lookup_vendor(device_info.mac_address)
                    if vendor and vendor != "Unknown Vendor":
                        self.device_repo.update_device_metadata(device['device_id'], vendor_name=vendor)
                    scan_results['devices_added'] += 1

                    # 2026-03-14: Record new_device event and alert for newly discovered devices
                    self._record_device_event(
                        device['device_id'],
                        'new_device',
                        f"New device discovered: {device_info.mac_address} ({device_info.ip_address})"
                    )

                online_macs.add(device_info.mac_address)

            # ── Deco client list supplement ──────────────────────────────────
            # The Deco router (DHCP server/gateway) knows every connected client.
            # Devices that don't respond to ARP/nmap probes but are connected
            # to WiFi or Ethernet will appear here.
            if self._deco_client:
                try:
                    deco_clients = self._deco_client.get_client_list_local()
                    for client in deco_clients:
                        client_mac_raw = client.get("mac", "") or client.get("macAddress", "")
                        client_ip = client.get("ip", "") or client.get("ipAddress", "")
                        if not client_mac_raw:
                            continue
                        # Normalize MAC to aa:bb:cc:dd:ee:ff
                        mac_clean = client_mac_raw.lower().replace("-", "").replace(":", "").replace(" ", "")
                        if len(mac_clean) != 12:
                            continue
                        normalized_mac = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))

                        if normalized_mac not in online_macs:
                            # Device is on Deco but not found by ARP scan — mark it online
                            existing = self.get_device_by_mac(normalized_mac)
                            if existing:
                                self.create_or_update_device(normalized_mac, client_ip or existing.get('current_ip'))
                            else:
                                device = self.create_or_update_device(normalized_mac, client_ip)
                                vendor = self.oui_service.lookup_vendor(normalized_mac)
                                if vendor and vendor != "Unknown Vendor":
                                    self.device_repo.update_device_metadata(device['device_id'], vendor_name=vendor)
                                scan_results['devices_added'] += 1

                            online_macs.add(normalized_mac)
                            scan_results['deco_online'] += 1

                    logger.info(f"Deco supplement: {scan_results['deco_online']} additional devices marked online")
                except Exception as e:
                    logger.warning(f"Deco client list supplement failed: {e}")

                # 2026-03-10: Also mark Deco node MACs as online — they're routers, not clients,
                # so they never appear in the client list but they are definitely online.
                try:
                    deco_nodes = self._deco_client.get_node_list()
                    for node in deco_nodes:
                        node_mac_raw = node.get("deviceMac", "") or node.get("mac", "")
                        if not node_mac_raw:
                            continue
                        mac_clean = node_mac_raw.lower().replace("-", "").replace(":", "").replace(" ", "")
                        if len(mac_clean) != 12:
                            continue
                        normalized_mac = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                        online_macs.add(normalized_mac)
                    logger.info(f"Deco node MACs added to online set: {len(deco_nodes)} nodes")
                except Exception as e:
                    logger.debug(f"Failed to fetch Deco node MACs for online set: {e}")

            # 2026-03-11: Also check Chester 5G router reachability — it's the gateway
            # (upstream of Deco) so it never appears in the Deco client list.
            try:
                from routes.chester import chester_service as _chester_svc
                if _chester_svc:
                    chester_status = _chester_svc.get_router_status()
                    if chester_status and chester_status.get("board"):
                        # Chester is responding — find its MAC from DB or known value
                        chester_mac_raw = chester_status["board"].get("mac", "")
                        if chester_mac_raw:
                            mac_clean = chester_mac_raw.lower().replace("-", "").replace(":", "").replace(" ", "")
                            if len(mac_clean) == 12:
                                chester_mac = ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
                                online_macs.add(chester_mac)
                                # Also update IP and last_seen
                                chester_ip = chester_status.get("ipv4_addr") or "192.168.12.1"
                                self.create_or_update_device(chester_mac, chester_ip)
                                logger.info(f"Chester 5G router confirmed online: {chester_mac}")
            except Exception as e:
                logger.debug(f"Chester reachability check failed: {e}")

            scan_results['devices_found'] = len(online_macs)

            # 2026-03-14: Detect state transitions and create events
            # Track devices that came online vs were already online
            all_online = self.list_online_devices()
            devices_now_offline = []

            for device in all_online:
                if device['mac_address'] not in online_macs:
                    # Device was online but is now offline
                    self.mark_offline(device['device_id'])
                    devices_now_offline.append(device)
                    scan_results['devices_offline'] += 1
                    # Record disconnected event
                    self._record_device_event(
                        device['device_id'],
                        'disconnected',
                        f"Device went offline (was {device.get('friendly_name') or device.get('mac_address')})"
                    )

            # Also check for devices that just came online (were offline but in online_macs)
            all_offline = self.list_offline_devices()
            for device in all_offline:
                if device['mac_address'] in online_macs:
                    # Device was offline but is now online
                    self.mark_online(device['device_id'])
                    # Record connected event
                    self._record_device_event(
                        device['device_id'],
                        'connected',
                        f"Device came online (was {device.get('friendly_name') or device.get('mac_address')})"
                    )

            # Update last scan timestamp
            self.config_repo.update_last_scan(datetime.utcnow())

            end_time = datetime.utcnow()
            scan_results['scan_time_seconds'] = (end_time - start_time).total_seconds()

            logger.info(f"Scan update completed: {scan_results}")

        except Exception as e:
            logger.error(f"Error in scan_and_update: {e}")
            scan_results['error'] = str(e)

        return scan_results

    def get_polling_config(self) -> dict:
        """Get polling configuration"""
        return self.config_repo.get_config()

    def set_polling_interval(self, interval_seconds: int) -> dict:
        """Set polling interval"""
        return self.config_repo.set_interval(interval_seconds)

    def update_device_vendor(self, device_id: str, vendor_name: str) -> Optional[dict]:
        """Update device vendor name"""
        return self.device_repo.update_device_metadata(device_id, vendor_name=vendor_name)

    def update_device_friendly_name(self, device_id: str, friendly_name: str) -> Optional[dict]:
        """Update device friendly name"""
        return self.device_repo.update_device_metadata(device_id, friendly_name=friendly_name)

    def update_device_type(self, device_id: str, device_type: str) -> Optional[dict]:
        """Update device type"""
        return self.device_repo.update_device_metadata(device_id, device_type=device_type)

    def set_device_notes(self, device_id: str, notes: str) -> Optional[dict]:
        """Set device notes"""
        return self.device_repo.update_device_metadata(device_id, notes=notes)

    def lookup_vendor_by_mac(self, mac_address: str) -> str:
        """Lookup vendor name by MAC address"""
        return self.oui_service.lookup_vendor(mac_address)

    def create_device_with_vendor(self, mac_address: str, ip_address: Optional[str] = None) -> dict:
        """Create device and auto-populate vendor from MAC address"""
        device = self.create_or_update_device(mac_address, ip_address)
        vendor_name = self.oui_service.lookup_vendor(mac_address)
        if vendor_name != "Unknown Vendor":
            device = self.device_repo.update_device_metadata(device['device_id'], vendor_name=vendor_name)
        return device
