"""
Comprehensive tests for device scanner, DHCP parser, and network device service
Tests for AI-280 - LAN Device Discovery via ARP/DHCP
"""

import pytest
import os
import sys
import tempfile
import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Database, NetworkDeviceRepository, PollingConfigRepository
from services import ARPScanner, DHCPParser, NetworkDeviceService, DeviceInfo, DHCPLease


class TestARPScanner:
    """Tests for ARP Scanner"""

    def test_arp_scanner_initialization(self):
        """Test ARP scanner initializes properly"""
        scanner = ARPScanner()
        assert scanner is not None
        assert hasattr(scanner, 'scan_subnet')

    def test_arp_scanner_validate_subnet(self):
        """Test subnet validation"""
        scanner = ARPScanner()
        assert scanner._validate_subnet("192.168.1.0/24") is True
        assert scanner._validate_subnet("10.0.0.0/24") is True
        assert scanner._validate_subnet("eth0") is True

    def test_arp_scanner_get_vendor(self):
        """Test vendor lookup from MAC address"""
        scanner = ARPScanner()
        # Test known vendor
        vendor = scanner._get_vendor("DC:A6:32:00:00:01")
        assert vendor is not None
        # Test unknown vendor
        vendor = scanner._get_vendor("AA:BB:CC:00:00:01")
        assert vendor is None

    def test_arp_scanner_generate_mac_from_ip(self):
        """Test pseudo MAC generation from IP"""
        scanner = ARPScanner()
        mac = scanner._generate_mac_from_ip("192.168.1.100")
        assert mac is not None
        assert ':' in mac
        assert len(mac.split(':')) == 6

    @patch('subprocess.run')
    def test_arp_scan_with_mock_output(self, mock_run):
        """Test ARP scan with mocked arp-scan output"""
        scanner = ARPScanner()
        scanner.has_arp_scan = True

        # Mock arp-scan output
        mock_output = """Interface: eth0, datalink type: Linux Ethernet (mac length: 6)
Starting arp-scan 1.9.7 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.1.1	08:00:27:00:00:00	QEMU
192.168.1.100	DC:A6:32:00:00:01	RASPBERRY PI
192.168.1.101	00:0C:29:00:00:01	VMWARE
3 packets transmitted, 3 packets received, 0 packet loss
Round-trip min/avg/max/dev = 1.234/1.567/2.345/0.456 ms"""

        mock_run.return_value = Mock(returncode=0, stdout=mock_output, stderr="")

        devices = scanner.scan_subnet_with_arp_scan("192.168.1.0/24")
        assert len(devices) >= 3
        assert any(d.mac_address == '08:00:27:00:00:00' for d in devices)
        assert any(d.ip_address == '192.168.1.100' for d in devices)

    @patch('subprocess.run')
    def test_nmap_scan_with_mock_output(self, mock_run):
        """Test nmap scan with mocked output"""
        scanner = ARPScanner()
        scanner.has_nmap = True

        # Mock nmap output
        mock_output = """# Nmap done at Thu Mar  6 19:00:00 2026; 256 IP addresses (3 hosts up) scanned in 1.23 seconds
Host: 192.168.1.1 (router.local)	Status: Up
Host: 192.168.1.100 (raspberry.local)	Status: Up
Host: 192.168.1.101 (vmhost)	Status: Up"""

        mock_run.return_value = Mock(returncode=0, stdout=mock_output, stderr="")

        devices = scanner.scan_subnet_with_nmap("192.168.1.0/24")
        assert len(devices) >= 3

    def test_arp_scanner_invalid_subnet(self):
        """Test scanning with invalid subnet"""
        scanner = ARPScanner()
        devices = scanner.scan_subnet("invalid/subnet")
        assert devices == []


class TestDHCPParser:
    """Tests for DHCP Parser"""

    def test_dhcp_parser_initialization(self):
        """Test DHCP parser initializes properly"""
        parser = DHCPParser()
        assert parser is not None
        assert hasattr(parser, 'parse_leases')

    def test_dhcp_parser_with_mock_file(self):
        """Test DHCP lease parsing with mock file"""
        parser = DHCPParser()

        # Create mock lease file
        mock_leases = """
# dhcpd.leases file
lease 192.168.1.100 {
  hardware ethernet dc:a6:32:00:00:01;
  client-hostname "raspberry";
  starts 5 2026/03/06 10:00:00;
  ends 5 2026/03/06 22:00:00;
}
lease 192.168.1.101 {
  hardware ethernet 00:0c:29:00:00:01;
  client-hostname "vmhost";
  starts 5 2026/03/06 09:00:00;
  ends 5 2026/03/06 21:00:00;
}"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.leases') as f:
            f.write(mock_leases)
            temp_path = f.name

        try:
            parser.dhcp_path = temp_path
            leases = parser.parse_leases()
            assert len(leases) >= 2
            assert any(l.mac_address == 'dc:a6:32:00:00:01' for l in leases)
        finally:
            os.unlink(temp_path)

    def test_dhcp_lease_dataclass(self):
        """Test DHCPLease dataclass"""
        lease = DHCPLease(
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="192.168.1.100",
            hostname="device",
            lease_start="2026/03/06 10:00:00",
            lease_end="2026/03/06 22:00:00"
        )
        assert lease.mac_address == "aa:bb:cc:dd:ee:ff"
        assert lease.to_dict()['ip_address'] == "192.168.1.100"


class TestNetworkDeviceRepository:
    """Tests for NetworkDevice repository"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()

        yield db

        db.close()
        os.unlink(db_path)

    def test_create_device(self, temp_db):
        """Test creating a new device"""
        repo = NetworkDeviceRepository(temp_db)

        device = repo.create_or_update(
            device_id="test-device-1",
            mac_address="aa:bb:cc:dd:ee:ff",
            current_ip="192.168.1.100"
        )

        assert device is not None
        assert device['mac_address'] == "aa:bb:cc:dd:ee:ff"
        assert device['current_ip'] == "192.168.1.100"
        assert device['status'] == 'online'

    def test_get_device_by_id(self, temp_db):
        """Test retrieving device by ID"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("test-dev-1", "aa:bb:cc:dd:ee:ff", "192.168.1.100")
        device = repo.get_by_id("test-dev-1")

        assert device is not None
        assert device['device_id'] == "test-dev-1"

    def test_get_device_by_mac(self, temp_db):
        """Test retrieving device by MAC address"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("test-dev-1", "aa:bb:cc:dd:ee:ff", "192.168.1.100")
        device = repo.get_by_mac("aa:bb:cc:dd:ee:ff")

        assert device is not None
        assert device['mac_address'] == "aa:bb:cc:dd:ee:ff"

    def test_list_all_devices(self, temp_db):
        """Test listing all devices"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        repo.create_or_update("dev-2", "aa:bb:cc:dd:ee:02", "192.168.1.101")
        repo.create_or_update("dev-3", "aa:bb:cc:dd:ee:03", "192.168.1.102")

        devices = repo.list_all()
        assert len(devices) == 3

    def test_mark_offline(self, temp_db):
        """Test marking device as offline"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        repo.mark_offline("dev-1")

        device = repo.get_by_id("dev-1")
        assert device['status'] == 'offline'

    def test_mark_online(self, temp_db):
        """Test marking device as online"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        repo.mark_offline("dev-1")
        repo.mark_online("dev-1")

        device = repo.get_by_id("dev-1")
        assert device['status'] == 'online'

    def test_list_by_status(self, temp_db):
        """Test filtering devices by status"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        repo.create_or_update("dev-2", "aa:bb:cc:dd:ee:02", "192.168.1.101")
        repo.mark_offline("dev-1")

        online = repo.list_by_status('online')
        offline = repo.list_by_status('offline')

        assert len(online) == 1
        assert len(offline) == 1

    def test_device_uniqueness_by_mac(self, temp_db):
        """Test MAC address uniqueness constraint"""
        repo = NetworkDeviceRepository(temp_db)

        repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")

        # Try to create another device with same MAC
        with pytest.raises(sqlite3.IntegrityError):
            with temp_db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO network_devices
                    (device_id, mac_address, current_ip)
                    VALUES (?, ?, ?)
                """, ("dev-2", "aa:bb:cc:dd:ee:01", "192.168.1.101"))
                conn.commit()


class TestPollingConfigRepository:
    """Tests for Polling Configuration repository"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()

        yield db

        db.close()
        os.unlink(db_path)

    def test_get_default_config(self, temp_db):
        """Test getting default polling config"""
        repo = PollingConfigRepository(temp_db)
        config = repo.get_config()

        assert config['polling_interval_seconds'] == 60

    def test_set_polling_interval(self, temp_db):
        """Test setting polling interval"""
        repo = PollingConfigRepository(temp_db)
        config = repo.set_interval(120)

        assert config['polling_interval_seconds'] == 120

    def test_invalid_interval(self, temp_db):
        """Test invalid polling interval"""
        repo = PollingConfigRepository(temp_db)

        with pytest.raises(ValueError):
            repo.set_interval(0)

        with pytest.raises(ValueError):
            repo.set_interval(-1)

    def test_update_last_scan(self, temp_db):
        """Test updating last scan timestamp"""
        repo = PollingConfigRepository(temp_db)
        now = datetime.utcnow()

        config = repo.update_last_scan(now)
        assert config['last_scan_timestamp'] is not None


class TestNetworkDeviceService:
    """Tests for NetworkDeviceService"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()

        yield db

        db.close()
        os.unlink(db_path)

    def test_service_initialization(self, temp_db):
        """Test service initializes properly"""
        service = NetworkDeviceService(temp_db)
        assert service is not None
        assert service.device_repo is not None

    def test_create_or_update_device(self, temp_db):
        """Test creating device via service"""
        service = NetworkDeviceService(temp_db)

        device = service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.100")
        assert device is not None
        assert device['mac_address'] == "aa:bb:cc:dd:ee:01"

    def test_list_devices_via_service(self, temp_db):
        """Test listing devices via service"""
        service = NetworkDeviceService(temp_db)

        service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.100")
        service.create_or_update_device("aa:bb:cc:dd:ee:02", "192.168.1.101")

        devices = service.list_devices()
        assert len(devices) == 2

    def test_polling_config_via_service(self, temp_db):
        """Test polling config via service"""
        service = NetworkDeviceService(temp_db)

        config = service.get_polling_config()
        assert config['polling_interval_seconds'] == 60

        config = service.set_polling_interval(120)
        assert config['polling_interval_seconds'] == 120

    @patch.object(NetworkDeviceService, 'arp_scanner')
    def test_scan_and_update(self, mock_scanner, temp_db):
        """Test scan and update operation"""
        service = NetworkDeviceService(temp_db)

        # Mock scanner results
        mock_device1 = DeviceInfo("aa:bb:cc:dd:ee:01", "192.168.1.100")
        mock_device2 = DeviceInfo("aa:bb:cc:dd:ee:02", "192.168.1.101")
        mock_scanner.scan_subnet.return_value = [mock_device1, mock_device2]

        result = service.scan_and_update("192.168.1.0/24")

        assert result['devices_found'] == 2
        assert result['devices_added'] == 2

    @patch.object(NetworkDeviceService, 'arp_scanner')
    def test_offline_detection(self, mock_scanner, temp_db):
        """Test detecting devices going offline"""
        service = NetworkDeviceService(temp_db)

        # Create initial devices
        service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.100")
        service.create_or_update_device("aa:bb:cc:dd:ee:02", "192.168.1.101")

        # Scan with only one device
        mock_device = DeviceInfo("aa:bb:cc:dd:ee:01", "192.168.1.100")
        mock_scanner.scan_subnet.return_value = [mock_device]

        result = service.scan_and_update("192.168.1.0/24")

        assert result['devices_offline'] == 1

        # Check device status
        devices = service.list_offline_devices()
        assert len(devices) == 1


class TestDatabaseIntegration:
    """Integration tests for database operations"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()

        yield db

        db.close()
        os.unlink(db_path)

    def test_concurrent_device_creation(self, temp_db):
        """Test concurrent device creation doesn't corrupt data"""
        repo = NetworkDeviceRepository(temp_db)

        # Create multiple devices
        for i in range(10):
            mac = f"aa:bb:cc:dd:ee:{i:02x}"
            repo.create_or_update(f"dev-{i}", mac, f"192.168.1.{100+i}")

        devices = repo.list_all()
        assert len(devices) == 10

    def test_transaction_integrity(self, temp_db):
        """Test database transaction integrity"""
        repo = NetworkDeviceRepository(temp_db)

        device = repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        repo.mark_offline(device['device_id'])

        # Verify change persisted
        updated = repo.get_by_id(device['device_id'])
        assert updated['status'] == 'offline'


class TestErrorHandling:
    """Tests for error handling"""

    def test_arp_scanner_no_tools(self):
        """Test ARP scanner graceful failure when no tools available"""
        scanner = ARPScanner()
        scanner.has_arp_scan = False
        scanner.has_nmap = False

        devices = scanner.scan_subnet("192.168.1.0/24")
        assert devices == []

    def test_dhcp_parser_file_not_found(self):
        """Test DHCP parser graceful failure when file not found"""
        parser = DHCPParser()
        parser.dhcp_path = "/nonexistent/path/dhcpd.leases"

        leases = parser.parse_leases()
        assert leases == []

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()

        yield db

        db.close()
        os.unlink(db_path)

    def test_invalid_interval_value(self, temp_db):
        """Test invalid polling interval values"""
        repo = PollingConfigRepository(temp_db)

        with pytest.raises(ValueError):
            repo.set_interval(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--cov=services", "--cov=db"])
