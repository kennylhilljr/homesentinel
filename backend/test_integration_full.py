#!/usr/bin/env python3
"""Full integration test with sample data"""

import sys
import os
from datetime import datetime
from unittest.mock import Mock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import Database, NetworkDeviceRepository
from services.deco_service import DecoService
from services.correlation_service import CorrelationService

def test_full_integration():
    """Test full correlation flow with real database"""

    # Create database and repository
    db = Database()
    device_repo = NetworkDeviceRepository(db)

    # Create test devices in database
    test_devices = [
        {
            "device_id": "test-iphone",
            "mac_address": "AA:BB:CC:DD:EE:01",
            "current_ip": "192.168.1.100",
            "vendor_name": "APPLE",
            "friendly_name": "John iPhone",
            "status": "online",
        },
        {
            "device_id": "test-laptop",
            "mac_address": "AA:BB:CC:DD:EE:02",
            "current_ip": "192.168.1.101",
            "vendor_name": "DELL",
            "friendly_name": "Work Laptop",
            "status": "online",
        },
        {
            "device_id": "test-tablet",
            "mac_address": "AA:BB:CC:DD:EE:03",
            "current_ip": "192.168.1.102",
            "vendor_name": "SAMSUNG",
            "friendly_name": "Tablet",
            "status": "online",
        },
        {
            "device_id": "test-router",
            "mac_address": "AA:BB:CC:DD:EE:04",
            "current_ip": "192.168.1.1",
            "vendor_name": "TP-LINK",
            "friendly_name": "Router",
            "status": "online",
        },
        {
            "device_id": "test-printer",
            "mac_address": "AA:BB:CC:DD:EE:05",
            "current_ip": "192.168.1.50",
            "vendor_name": "HP",
            "friendly_name": "Printer",
            "status": "offline",
        },
        {
            "device_id": "test-camera",
            "mac_address": "AA:BB:CC:DD:EE:06",
            "current_ip": "192.168.1.51",
            "vendor_name": "HIKVISION",
            "friendly_name": "Camera",
            "status": "online",
        },
    ]

    print("Creating test devices in database...")
    for device_data in test_devices:
        device_repo.create_or_update(
            device_data["device_id"],
            device_data["mac_address"],
            device_data["current_ip"]
        )
        # Update metadata
        device_repo.update_device_metadata(
            device_data["device_id"],
            friendly_name=device_data["friendly_name"],
            vendor_name=device_data["vendor_name"]
        )

    # Create mock Deco service and client
    mock_deco_service = Mock()
    mock_deco_client = Mock()

    # Create Deco client data (matching some of the LAN devices)
    deco_clients = [
        {"macAddress": "AA:BB:CC:DD:EE:01", "clientName": "iPhone (John)"},
        {"macAddress": "AA:BB:CC:DD:EE:02", "clientName": "Laptop"},
        {"macAddress": "AA:BB:CC:DD:EE:03", "clientName": "Tablet"},
        {"macAddress": "AA:BB:CC:DD:EE:04", "clientName": "Main Router"},
        {"macAddress": "AA:BB:CC:DD:EE:06", "clientName": "Security Camera"},
        # This one is not in database
        {"macAddress": "AA:BB:CC:DD:EE:99", "clientName": "Guest Device"},
    ]

    mock_deco_client.get_client_list.return_value = deco_clients
    mock_deco_service.deco_client = mock_deco_client

    # Create correlation service
    correlation_service = CorrelationService(mock_deco_service, device_repo)

    # Get merged clients
    print("\nCorrelating Deco clients with LAN devices...")
    result = correlation_service.get_merged_clients()

    # Display results
    print(f"\nResults:")
    print(f"  Total Deco clients: {result['correlation_stats']['total_deco_clients']}")
    print(f"  Total LAN devices: {result['correlation_stats']['total_lan_devices']}")
    print(f"  Successfully merged: {result['total_merged']}")
    print(f"  Correlation percentage: {result['correlation_stats']['correlation_percentage']}%")
    print(f"  Unmatched Deco clients: {result['unmatched_deco_count']}")
    print(f"  Unmatched LAN devices: {result['unmatched_lan_devices']}")

    print(f"\nMerged Devices ({len(result['merged_devices'])} total):")
    for device in result['merged_devices']:
        status_icon = "✓" if device['status'] == 'online' else "✗"
        vendor = device.get('vendor_name') or 'N/A'
        friendly = device.get('friendly_name') or 'N/A'
        print(f"  {status_icon} {device['deco_client_name']:<20} | {device['current_ip']:<15} | {vendor:<10} | {friendly}")

    if result['unmatched_deco_clients']:
        print(f"\nUnmatched Deco Clients ({len(result['unmatched_deco_clients'])} total):")
        for client in result['unmatched_deco_clients']:
            print(f"  - {client['clientName']} ({client['macAddress']})")

    # Verify results
    print("\n" + "=" * 60)
    print("Verification:")

    # Should have 5 merged devices (all LAN devices except printer which has no Deco client)
    assert result['total_merged'] == 5, f"Expected 5 merged devices, got {result['total_merged']}"
    print("✓ Correct number of merged devices (5)")

    # Should have 1 unmatched Deco client (Guest Device)
    assert result['unmatched_deco_count'] == 1, f"Expected 1 unmatched Deco client, got {result['unmatched_deco_count']}"
    print("✓ Correct number of unmatched Deco clients (1)")

    # Should have 1 unmatched LAN device (Printer)
    assert result['unmatched_lan_devices'] == 1, f"Expected 1 unmatched LAN device, got {result['unmatched_lan_devices']}"
    print("✓ Correct number of unmatched LAN devices (1)")

    # Verify merged device has both Deco and LAN data
    iphone = next((d for d in result['merged_devices'] if d['device_id'] == 'test-iphone'), None)
    assert iphone is not None, "iPhone device not found"
    assert iphone['deco_client_name'] == "iPhone (John)", "Deco client name missing"
    assert iphone['current_ip'] == "192.168.1.100", "IP address incorrect"
    assert iphone['vendor_name'] == "APPLE", "Vendor name incorrect"
    assert iphone['friendly_name'] == "John iPhone", "Friendly name incorrect"
    print("✓ Merged device has both Deco and LAN data")

    # Verify online devices come first
    online_devices = [d for d in result['merged_devices'] if d['status'] == 'online']
    offline_devices = [d for d in result['merged_devices'] if d['status'] == 'offline']
    assert len(online_devices) == 5, "Should have 5 online devices"
    assert len(offline_devices) == 0, "Should have 0 offline devices"
    print("✓ Devices properly sorted by status")

    # Verify response structure
    assert 'timestamp' in result, "Response missing timestamp"
    assert 'correlation_stats' in result, "Response missing correlation_stats"
    print("✓ Response structure is complete")

    print("\n" + "=" * 60)
    print("Full integration test PASSED! ✓")

    # Cleanup
    db.close()


if __name__ == "__main__":
    try:
        test_full_integration()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
