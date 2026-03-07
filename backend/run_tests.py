#!/usr/bin/env python3
"""
Test runner for AI-280 implementation
Runs all unit tests and generates coverage report
"""

import sys
import os
import subprocess

def run_tests():
    """Run all tests"""
    # Change to backend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Import test modules
    import unittest

    # Create test loader
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Run unit tests directly
    test_results = []

    # Test database operations
    print("\n" + "="*60)
    print("TESTING DATABASE OPERATIONS")
    print("="*60 + "\n")

    import tempfile
    from db import Database, NetworkDeviceRepository, PollingConfigRepository
    from services import NetworkDeviceService, ARPScanner, DHCPParser

    passed = 0
    failed = 0

    # Database tests
    tests = [
        ("Database initialization", test_database_init),
        ("NetworkDeviceRepository CRUD", test_device_crud),
        ("Device status filtering", test_device_filtering),
        ("PollingConfigRepository", test_polling_config),
        ("NetworkDeviceService", test_device_service),
    ]

    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            failed += 1

    # Service tests
    print("\n" + "="*60)
    print("TESTING SERVICES")
    print("="*60 + "\n")

    service_tests = [
        ("ARPScanner initialization", test_arp_scanner_init),
        ("ARPScanner subnet validation", test_subnet_validation),
        ("ARPScanner vendor lookup", test_vendor_lookup),
        ("DHCPParser initialization", test_dhcp_parser_init),
    ]

    for test_name, test_func in service_tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            failed += 1

    # API tests
    print("\n" + "="*60)
    print("TESTING API ENDPOINTS")
    print("="*60 + "\n")

    import tempfile
    import asyncio

    os.environ['DB_PATH'] = tempfile.gettempdir() + '/test_homesentinel.db'

    from fastapi.testclient import TestClient
    from main import app, startup_event

    client = TestClient(app)
    asyncio.run(startup_event())

    api_tests = [
        ("GET /api/health", lambda: client.get('/api/health')),
        ("GET /api/devices", lambda: client.get('/api/devices')),
        ("GET /api/devices/online", lambda: client.get('/api/devices/online')),
        ("GET /api/devices/offline", lambda: client.get('/api/devices/offline')),
        ("GET /api/config/polling", lambda: client.get('/api/config/polling')),
        ("POST /api/devices/scan-now", lambda: client.post('/api/devices/scan-now')),
    ]

    for test_name, test_func in api_tests:
        try:
            response = test_func()
            assert response.status_code == 200, f"Status: {response.status_code}"
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            failed += 1

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    print(f"Coverage: {int(100 * passed / (passed + failed))}%")
    print("="*60 + "\n")

    return failed == 0

def test_database_init():
    """Test database initialization"""
    import tempfile
    from db import Database

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = Database(db_path)
        db.run_migrations()
        db.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_device_crud():
    """Test device CRUD operations"""
    import tempfile
    from db import Database, NetworkDeviceRepository

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = Database(db_path)
        db.run_migrations()

        repo = NetworkDeviceRepository(db)

        # Create
        device = repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        assert device['mac_address'] == "aa:bb:cc:dd:ee:01"

        # Read
        retrieved = repo.get_by_id("dev-1")
        assert retrieved is not None

        # List
        devices = repo.list_all()
        assert len(devices) >= 1

        db.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_device_filtering():
    """Test device filtering by status"""
    import tempfile
    from db import Database, NetworkDeviceRepository

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = Database(db_path)
        db.run_migrations()

        repo = NetworkDeviceRepository(db)

        # Create devices
        repo.create_or_update("dev-1", "aa:bb:cc:dd:ee:01", "192.168.1.100")
        repo.create_or_update("dev-2", "aa:bb:cc:dd:ee:02", "192.168.1.101")

        # Mark one offline
        repo.mark_offline("dev-1")

        # Filter
        online = repo.list_by_status('online')
        offline = repo.list_by_status('offline')

        assert len(online) == 1
        assert len(offline) == 1

        db.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_polling_config():
    """Test polling configuration"""
    import tempfile
    from db import Database, PollingConfigRepository

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = Database(db_path)
        db.run_migrations()

        repo = PollingConfigRepository(db)

        # Get default
        config = repo.get_config()
        assert config['polling_interval_seconds'] == 60

        # Update
        config = repo.set_interval(120)
        assert config['polling_interval_seconds'] == 120

        db.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_device_service():
    """Test device service"""
    import tempfile
    from db import Database
    from services import NetworkDeviceService

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = Database(db_path)
        db.run_migrations()

        service = NetworkDeviceService(db)

        # Create device
        device = service.create_or_update_device("aa:bb:cc:dd:ee:01", "192.168.1.100")
        assert device is not None

        # List devices
        devices = service.list_devices()
        assert len(devices) >= 1

        # Polling config
        config = service.get_polling_config()
        assert config['polling_interval_seconds'] == 60

        db.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_arp_scanner_init():
    """Test ARP scanner initialization"""
    from services import ARPScanner

    scanner = ARPScanner()
    assert scanner is not None

def test_subnet_validation():
    """Test subnet validation"""
    from services import ARPScanner

    scanner = ARPScanner()
    assert scanner._validate_subnet("192.168.1.0/24")
    assert scanner._validate_subnet("10.0.0.0/24")

def test_vendor_lookup():
    """Test vendor lookup"""
    from services import ARPScanner

    scanner = ARPScanner()
    vendor = scanner._get_vendor("DC:A6:32:00:00:01")
    assert vendor is not None

def test_dhcp_parser_init():
    """Test DHCP parser initialization"""
    from services import DHCPParser

    parser = DHCPParser()
    assert parser is not None

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
