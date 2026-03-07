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
            # arp-scan requires root privileges
            cmd = ['sudo', 'arp-scan', '-l', subnet]
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

    def scan_subnet_with_nmap(self, subnet: str) -> List[DeviceInfo]:
        """Scan subnet using nmap"""
        devices = []
        try:
            # Use nmap -sn for ping scan (fast ARP-based discovery)
            cmd = ['nmap', '-sn', subnet, '-oG', '-']
            result = subprocess.run(cmd, capture_output=True, timeout=60, text=True)

            if result.returncode != 0 and result.returncode != 1:
                logger.warning(f"nmap scan had issues: {result.stderr}")

            # Parse nmap output
            # Format: Host: IP (hostname) Status
            for line in result.stdout.split('\n'):
                if line.startswith('Host:'):
                    # Extract IP
                    match = re.search(r'Host:\s+([\d.]+)', line)
                    if match:
                        ip = match.group(1)

                        # Extract hostname if present
                        hostname_match = re.search(r'\((.*?)\)', line)
                        hostname = hostname_match.group(1) if hostname_match else None

                        # For nmap, we need to get MAC address separately
                        # This is a limitation - nmap -sn may not show MAC addresses
                        # For now, generate a pseudo MAC based on IP
                        mac = self._generate_mac_from_ip(ip)

                        device = DeviceInfo(
                            mac_address=mac,
                            ip_address=ip,
                            hostname=hostname
                        )
                        devices.append(device)
                        logger.debug(f"Discovered device: {ip}")

        except subprocess.TimeoutExpired:
            logger.error("nmap scan timed out")
        except Exception as e:
            logger.error(f"Error scanning with nmap: {e}")

        return devices

    def _generate_mac_from_ip(self, ip_address: str) -> str:
        """Generate a pseudo MAC address from IP (for testing purposes)"""
        # Extract last two octets from IP
        parts = ip_address.split('.')
        if len(parts) == 4:
            # Use last 4 octets to generate a MAC-like string
            mac = f"02:{parts[1]}:{parts[2]}:{parts[3]}:00:01"
            return mac
        return "02:00:00:00:00:01"

    def scan_subnet(self, subnet: str) -> List[DeviceInfo]:
        """Scan a subnet for devices (/24 CIDR notation)"""
        logger.info(f"Starting subnet scan: {subnet}")

        # Validate subnet format
        if not self._validate_subnet(subnet):
            logger.error(f"Invalid subnet format: {subnet}")
            return []

        devices = []

        # Try arp-scan first, then nmap
        if self.has_arp_scan:
            devices = self.scan_subnet_with_arp_scan(subnet)
        elif self.has_nmap:
            devices = self.scan_subnet_with_nmap(subnet)
        else:
            logger.error("No scanning tool available (arp-scan or nmap)")
            return []

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

    def create_or_update_device(self, mac_address: str, ip_address: Optional[str] = None) -> dict:
        """Create or update a network device"""
        # Generate device ID from MAC address
        device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac_address))

        return self.device_repo.create_or_update(device_id, mac_address, ip_address)

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
        """Scan subnet and update device database"""
        start_time = datetime.utcnow()
        scan_results = {
            'devices_found': 0,
            'devices_added': 0,
            'devices_updated': 0,
            'devices_offline': 0,
            'timestamp': start_time.isoformat(),
            'scan_time_seconds': 0
        }

        try:
            # Scan for devices
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
                    # Create new device
                    self.create_or_update_device(device_info.mac_address, device_info.ip_address)
                    scan_results['devices_added'] += 1

                online_macs.add(device_info.mac_address)

            # Mark devices as offline if not in scan results
            all_online = self.list_online_devices()
            for device in all_online:
                if device['mac_address'] not in online_macs:
                    self.mark_offline(device['device_id'])
                    scan_results['devices_offline'] += 1

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
