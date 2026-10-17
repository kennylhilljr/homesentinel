#!/usr/bin/env python3
"""Simple test runner for correlation service tests"""

import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.correlation_service import CorrelationService
from services.deco_service import DecoService

def test_mac_normalization():
    """Test MAC address normalization"""
    mock_deco_service = Mock()
    mock_device_repo = Mock()
    service = CorrelationService(mock_deco_service, mock_device_repo)

    # Test various formats
    tests = [
        ("00:11:22:33:44:55", "00:11:22:33:44:55"),
        ("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
        ("AA-BB-CC-DD-EE-FF", "aa:bb:cc:dd:ee:ff"),
        ("AABBCCDDEEFF", "aa:bb:cc:dd:ee:ff"),
        ("Aa:Bb:Cc:Dd:Ee:Ff", "aa:bb:cc:dd:ee:ff"),
        ("", ""),
    ]

    for input_mac, expected in tests:
        result = service.normalize_mac_address(input_mac)
        assert result == expected, f"Failed: {input_mac} -> {result} (expected {expected})"
        print(f"✓ MAC normalization: {input_mac} -> {result}")


def test_correlation_with_matching_devices():
    """Test correlation of matching Deco clients and LAN devices"""
    mock_deco_service = Mock()
    mock_device_repo = Mock()
    service = CorrelationService(mock_deco_service, mock_device_repo)

    deco_clients = [
        {"macAddress": "00:11:22:33:44:55", "clientName": "iPhone"}
    ]

    lan_devices = [
        {
            "device_id": "device1",
            "mac_address": "00:11:22:33:44:55",
            "current_ip": "192.168.1.50",
            "vendor_name": "APPLE",
            "friendly_name": "john-iphone",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }
    ]

    merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
        deco_clients, lan_devices
    )

    assert len(merged) == 1
    assert merged[0]["device_id"] == "device1"
    assert merged[0]["deco_client_name"] == "iPhone"
    assert merged[0]["current_ip"] == "192.168.1.50"
    assert len(unmatched_deco) == 0
    assert len(unmatched_lan) == 0
    print("✓ Correlation with matching devices passed")


def test_correlation_with_format_variations():
    """Test correlation works with different MAC formats"""
    mock_deco_service = Mock()
    mock_device_repo = Mock()
    service = CorrelationService(mock_deco_service, mock_device_repo)

    deco_clients = [
        {"macAddress": "00-11-22-33-44-55", "clientName": "Laptop"}
    ]

    lan_devices = [
        {
            "device_id": "device1",
            "mac_address": "00:11:22:33:44:55",
            "current_ip": "192.168.1.100",
            "vendor_name": "DELL",
            "friendly_name": "work-laptop",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }
    ]

    merged, _, _ = service.correlate_by_mac(deco_clients, lan_devices)

    assert len(merged) == 1
    assert merged[0]["deco_client_name"] == "Laptop"
    print("✓ Correlation with MAC format variations passed")


def test_correlation_with_multiple_devices():
    """Test correlation with 5+ devices"""
    mock_deco_service = Mock()
    mock_device_repo = Mock()
    service = CorrelationService(mock_deco_service, mock_device_repo)

    # Create 6 Deco clients
    deco_clients = [
        {"macAddress": f"00:11:22:33:44:{i:02x}", "clientName": f"Device{i}"}
        for i in range(6)
    ]

    # Create 5 matching LAN devices
    lan_devices = [
        {
            "device_id": f"device{i}",
            "mac_address": f"00:11:22:33:44:{i:02x}",
            "current_ip": f"192.168.1.{50+i}",
            "vendor_name": "VENDOR",
            "friendly_name": f"device-{i}",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }
        for i in range(5)
    ]

    merged, unmatched_deco, unmatched_lan = service.correlate_by_mac(
        deco_clients, lan_devices
    )

    assert len(merged) == 5
    assert len(unmatched_deco) == 1
    assert len(unmatched_lan) == 0
    print("✓ Correlation with 5+ devices passed")


def test_get_merged_clients():
    """Test get_merged_clients method"""
    mock_deco_service = Mock()
    mock_deco_client = Mock()

    deco_clients = [
        {"macAddress": "00:11:22:33:44:55", "clientName": "iPhone"},
        {"macAddress": "AA:BB:CC:DD:EE:FF", "clientName": "Laptop"},
    ]

    mock_deco_client.get_client_list.return_value = deco_clients
    mock_deco_service.deco_client = mock_deco_client

    mock_device_repo = Mock()
    lan_devices = [
        {
            "device_id": "device1",
            "mac_address": "00:11:22:33:44:55",
            "current_ip": "192.168.1.50",
            "vendor_name": "APPLE",
            "friendly_name": "john-iphone",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }
    ]

    mock_device_repo.list_all.return_value = lan_devices

    service = CorrelationService(mock_deco_service, mock_device_repo)
    result = service.get_merged_clients()

    assert result["total_merged"] == 1
    assert result["unmatched_deco_count"] == 1
    assert result["unmatched_lan_devices"] == 0
    assert "correlation_stats" in result
    assert result["correlation_stats"]["correlation_percentage"] == 50.0
    assert "timestamp" in result
    print("✓ get_merged_clients passed")


def test_empty_data():
    """Test handling of empty data"""
    mock_deco_service = Mock()
    mock_deco_client = Mock()
    mock_deco_client.get_client_list.return_value = []
    mock_deco_service.deco_client = mock_deco_client

    mock_device_repo = Mock()
    mock_device_repo.list_all.return_value = []

    service = CorrelationService(mock_deco_service, mock_device_repo)
    result = service.get_merged_clients()

    assert result["total_merged"] == 0
    assert result["unmatched_deco_count"] == 0
    assert result["unmatched_lan_devices"] == 0
    assert result["correlation_stats"]["correlation_percentage"] == 0.0
    print("✓ Empty data handling passed")


def test_response_structure():
    """Test response structure"""
    mock_deco_service = Mock()
    mock_deco_client = Mock()
    mock_deco_client.get_client_list.return_value = [
        {"macAddress": "00:11:22:33:44:55", "clientName": "Device1"}
    ]
    mock_deco_service.deco_client = mock_deco_client

    mock_device_repo = Mock()
    mock_device_repo.list_all.return_value = [
        {
            "device_id": "device1",
            "mac_address": "00:11:22:33:44:55",
            "current_ip": "192.168.1.50",
            "vendor_name": "VENDOR",
            "friendly_name": "device1",
            "status": "online",
            "first_seen": "2026-03-01T10:00:00Z",
            "last_seen": "2026-03-07T02:23:00Z",
        }
    ]

    service = CorrelationService(mock_deco_service, mock_device_repo)
    result = service.get_merged_clients()

    # Verify response structure
    required_keys = [
        "merged_devices",
        "total_merged",
        "unmatched_deco_clients",
        "unmatched_deco_count",
        "unmatched_lan_devices",
        "timestamp",
        "correlation_stats",
    ]

    for key in required_keys:
        assert key in result, f"Missing key: {key}"

    # Verify merged device structure
    device = result["merged_devices"][0]
    required_device_keys = [
        "device_id",
        "mac_address",
        "current_ip",
        "deco_client_name",
        "vendor_name",
        "friendly_name",
        "status",
    ]

    for key in required_device_keys:
        assert key in device, f"Missing device key: {key}"

    print("✓ Response structure validation passed")


if __name__ == "__main__":
    print("Running Correlation Service Tests\n")
    print("=" * 50)

    try:
        test_mac_normalization()
        print()
        test_correlation_with_matching_devices()
        test_correlation_with_format_variations()
        test_correlation_with_multiple_devices()
        print()
        test_get_merged_clients()
        test_empty_data()
        test_response_structure()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
