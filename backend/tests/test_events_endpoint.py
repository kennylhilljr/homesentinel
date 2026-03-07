"""
Integration tests for event and alert API endpoints
"""

import pytest
import uuid
import tempfile
import os
import json
from datetime import datetime
from fastapi.testclient import TestClient
import sys

# Setup path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db import Database
from services.event_service import EventService


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(db_path=path)
    db.run_migrations()

    # Create test devices
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO network_devices (device_id, mac_address, status, friendly_name)
               VALUES (?, ?, ?, ?)""",
            ('device-1', 'AA:BB:CC:DD:EE:01', 'online', 'Test Device 1')
        )
        conn.execute(
            """INSERT INTO network_devices (device_id, mac_address, status, friendly_name)
               VALUES (?, ?, ?, ?)""",
            ('device-2', 'AA:BB:CC:DD:EE:02', 'offline', 'Test Device 2')
        )
        conn.commit()

    yield db

    # Cleanup
    db.close()
    os.unlink(path)


@pytest.fixture
def event_service(test_db):
    """Create EventService instance"""
    return EventService(test_db)


class TestEventEndpoints:
    """Tests for event endpoints"""

    def test_get_events_empty(self, event_service):
        """Test getting events when none exist"""
        events = event_service.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_get_events_after_recording(self, event_service):
        """Test retrieving events after recording"""
        event_service.record_event('device-1', 'online', 'Device came online')
        event_service.record_event('device-1', 'offline', 'Device went offline')

        events = event_service.get_events()
        assert len(events) == 2

    def test_get_events_filtered_by_device(self, event_service):
        """Test filtering events by device"""
        event_service.record_event('device-1', 'online')
        event_service.record_event('device-2', 'offline')

        device1_events = event_service.get_events(device_id='device-1')
        assert len(device1_events) == 1
        assert device1_events[0]['device_id'] == 'device-1'

    def test_get_events_filtered_by_type(self, event_service):
        """Test filtering events by type"""
        event_service.record_event('device-1', 'online')
        event_service.record_event('device-1', 'offline')
        event_service.record_event('device-1', 'online')

        online_events = event_service.get_events(event_type='online')
        assert len(online_events) == 2
        assert all(e['event_type'] == 'online' for e in online_events)

    def test_get_events_with_pagination(self, event_service):
        """Test event pagination"""
        for i in range(15):
            event_service.record_event('device-1', 'online')

        page1 = event_service.get_events(limit=10)
        assert len(page1) == 10

        page2 = event_service.get_events(limit=10, offset=10)
        assert len(page2) == 5


class TestAlertEndpoints:
    """Tests for alert endpoints"""

    def test_get_active_alerts(self, event_service):
        """Test retrieving active alerts"""
        # Create alerts
        event_id = event_service.record_event('device-1', 'new_device')
        event_service.create_alert('device-1', event_id, 'new_device')

        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 1
        assert alerts[0]['alert_type'] == 'new_device'

    def test_dismiss_alert_endpoint(self, event_service):
        """Test dismissing alert"""
        event_id = event_service.record_event('device-1', 'new_device')
        alert_id = event_service.create_alert('device-1', event_id, 'new_device')

        # Dismiss the alert
        event_service.dismiss_alert(alert_id)

        # Verify it's dismissed
        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 0

        dismissed = event_service.get_alerts(dismissed=True)
        assert len(dismissed) == 1

    def test_multiple_alerts(self, event_service):
        """Test managing multiple alerts"""
        # Create multiple alerts
        for i in range(3):
            event_id = event_service.record_event('device-1', 'new_device')
            event_service.create_alert('device-1', event_id, 'new_device')

        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 3

        # Dismiss one
        event_service.dismiss_alert(alerts[0]['alert_id'])

        # Verify
        active = event_service.get_alerts(dismissed=False)
        assert len(active) == 2


class TestEventStats:
    """Tests for event statistics endpoint"""

    def test_get_stats(self, event_service):
        """Test retrieving event statistics"""
        event_service.record_event('device-1', 'online')
        event_service.record_event('device-1', 'offline')
        event_service.record_event('device-2', 'online')

        stats = event_service.get_event_stats()

        assert stats['total_events'] == 3
        assert 'online' in stats['events_by_type']
        assert 'offline' in stats['events_by_type']
        assert stats['events_last_24h'] == 3

    def test_stats_with_alerts(self, event_service):
        """Test stats include alert count"""
        event_id = event_service.record_event('device-1', 'new_device')
        event_service.create_alert('device-1', event_id, 'new_device')

        stats = event_service.get_event_stats()
        assert stats['active_alerts'] == 1


class TestEventRecordingIntegration:
    """Integration tests for event recording"""

    def test_new_device_workflow(self, event_service):
        """Test complete new device workflow"""
        # Check if device is new
        is_new = event_service.detect_new_device('device-1')
        assert is_new is True

        # Record new device event
        event_id = event_service.record_event('device-1', 'new_device')
        assert event_id is not None

        # Create alert
        alert_id = event_service.create_alert('device-1', event_id, 'new_device')
        assert alert_id is not None

        # Verify alert is active
        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 1

        # Dismiss alert
        event_service.dismiss_alert(alert_id)

        # Verify alert is dismissed
        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 0

    def test_device_status_change_workflow(self, event_service):
        """Test device coming online/offline"""
        # Device comes online
        event_service.record_event('device-1', 'online')

        # Device goes offline
        event_service.record_event('device-1', 'offline')

        # Verify events recorded
        events = event_service.get_events(device_id='device-1')
        assert len(events) == 2

        # Verify event types
        event_types = [e['event_type'] for e in events]
        assert 'online' in event_types
        assert 'offline' in event_types

    def test_event_history_retention(self, event_service):
        """Test event history is retained for queries"""
        # Record many events
        for i in range(20):
            event_service.record_event('device-1', 'online' if i % 2 == 0 else 'offline')

        # Retrieve all events
        all_events = event_service.get_events()
        assert len(all_events) == 20

        # Count by type
        online_count = len([e for e in all_events if e['event_type'] == 'online'])
        offline_count = len([e for e in all_events if e['event_type'] == 'offline'])

        assert online_count == 10
        assert offline_count == 10


class TestEventValidation:
    """Tests for event data validation"""

    def test_record_event_with_all_fields(self, event_service):
        """Test recording event with all fields populated"""
        event_id = event_service.record_event(
            device_id='device-1',
            event_type='online',
            description='Device came online via DHCP',
            metadata='{"ip":"192.168.1.100","hostname":"mydevice"}'
        )

        events = event_service.get_events(limit=1)
        event = events[0]

        assert event['event_id'] == event_id
        assert event['device_id'] == 'device-1'
        assert event['event_type'] == 'online'
        assert event['description'] == 'Device came online via DHCP'
        assert '192.168.1.100' in event['metadata']

    def test_alert_alert_types(self, event_service):
        """Test different alert types"""
        alert_types = ['new_device', 'device_reconnected', 'device_offline']

        for alert_type in alert_types:
            event_id = event_service.record_event('device-1', alert_type)
            alert_id = event_service.create_alert('device-1', event_id, alert_type)
            assert alert_id is not None

        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 3
