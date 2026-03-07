"""
Unit tests for EventService
"""

import pytest
import uuid
import tempfile
import os
from datetime import datetime, timedelta
from db import Database
from services.event_service import EventService


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(db_path=path)
    db.run_migrations()

    # Create a test device first
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO network_devices (device_id, mac_address, status)
               VALUES (?, ?, ?)""",
            ('test-device-1', 'AA:BB:CC:DD:EE:FF', 'online')
        )
        conn.commit()

    yield db

    # Cleanup
    db.close()
    os.unlink(path)


@pytest.fixture
def event_service(test_db):
    """Create EventService instance with test database"""
    return EventService(test_db)


class TestEventRecording:
    """Tests for event recording functionality"""

    def test_record_event(self, event_service):
        """Test recording a device event"""
        event_id = event_service.record_event(
            device_id='test-device-1',
            event_type='connected',
            description='Device connected to network'
        )

        assert event_id is not None
        assert len(event_id) > 0

    def test_record_multiple_events(self, event_service):
        """Test recording multiple events"""
        event_ids = []
        for i in range(5):
            event_id = event_service.record_event(
                device_id='test-device-1',
                event_type='online' if i % 2 == 0 else 'offline'
            )
            event_ids.append(event_id)

        assert len(event_ids) == 5
        assert len(set(event_ids)) == 5  # All unique

    def test_record_event_with_metadata(self, event_service):
        """Test recording event with metadata"""
        metadata = '{"ip":"192.168.1.100"}'
        event_id = event_service.record_event(
            device_id='test-device-1',
            event_type='connected',
            metadata=metadata
        )

        events = event_service.get_events(event_id=event_id)
        assert len(events) > 0


class TestEventRetrieval:
    """Tests for event retrieval functionality"""

    def test_get_events_empty(self, event_service):
        """Test getting events when none exist"""
        events = event_service.get_events()
        assert isinstance(events, list)

    def test_get_events_by_device(self, event_service):
        """Test filtering events by device"""
        # Record some events
        for i in range(3):
            event_service.record_event(
                device_id='test-device-1',
                event_type='online'
            )

        events = event_service.get_events(device_id='test-device-1')
        assert len(events) == 3

    def test_get_events_by_type(self, event_service):
        """Test filtering events by type"""
        event_service.record_event('test-device-1', 'connected')
        event_service.record_event('test-device-1', 'online')
        event_service.record_event('test-device-1', 'connected')

        online_events = event_service.get_events(event_type='online')
        assert len(online_events) == 1

        connected_events = event_service.get_events(event_type='connected')
        assert len(connected_events) == 2

    def test_get_events_with_limit(self, event_service):
        """Test event retrieval with limit"""
        for i in range(10):
            event_service.record_event('test-device-1', 'online')

        events = event_service.get_events(limit=5)
        assert len(events) == 5

    def test_get_event_count(self, event_service):
        """Test getting event count"""
        for i in range(7):
            event_service.record_event('test-device-1', 'online')

        count = event_service.get_event_count()
        assert count == 7

    def test_get_event_count_filtered(self, event_service):
        """Test getting filtered event count"""
        event_service.record_event('test-device-1', 'connected')
        event_service.record_event('test-device-1', 'connected')
        event_service.record_event('test-device-1', 'online')

        count = event_service.get_event_count(event_type='connected')
        assert count == 2


class TestAlertManagement:
    """Tests for alert functionality"""

    def test_create_alert(self, event_service):
        """Test creating an alert"""
        event_id = event_service.record_event('test-device-1', 'new_device')
        alert_id = event_service.create_alert(
            device_id='test-device-1',
            event_id=event_id,
            alert_type='new_device'
        )

        assert alert_id is not None
        assert len(alert_id) > 0

    def test_get_active_alerts(self, event_service):
        """Test retrieving active alerts"""
        event_id = event_service.record_event('test-device-1', 'new_device')
        event_service.create_alert('test-device-1', event_id, 'new_device')

        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 1
        assert alerts[0]['dismissed'] is False

    def test_dismiss_alert(self, event_service):
        """Test dismissing an alert"""
        event_id = event_service.record_event('test-device-1', 'new_device')
        alert_id = event_service.create_alert('test-device-1', event_id, 'new_device')

        # Verify alert exists and is not dismissed
        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 1

        # Dismiss alert
        event_service.dismiss_alert(alert_id)

        # Verify alert is now dismissed
        alerts = event_service.get_alerts(dismissed=False)
        assert len(alerts) == 0

    def test_get_dismissed_alerts(self, event_service):
        """Test retrieving dismissed alerts"""
        event_id = event_service.record_event('test-device-1', 'new_device')
        alert_id = event_service.create_alert('test-device-1', event_id, 'new_device')

        event_service.dismiss_alert(alert_id)

        dismissed = event_service.get_alerts(dismissed=True)
        assert len(dismissed) == 1
        assert dismissed[0]['dismissed'] is True


class TestNewDeviceDetection:
    """Tests for new device detection"""

    def test_detect_new_device(self, event_service):
        """Test detecting a new device"""
        is_new = event_service.detect_new_device('test-device-1')
        assert is_new is True

    def test_detect_existing_device(self, event_service):
        """Test detecting an existing device (not new)"""
        event_service.record_event('test-device-1', 'connected')

        is_new = event_service.detect_new_device('test-device-1')
        assert is_new is False


class TestEventStats:
    """Tests for event statistics"""

    def test_get_event_stats(self, event_service):
        """Test getting event statistics"""
        event_service.record_event('test-device-1', 'connected')
        event_service.record_event('test-device-1', 'online')
        event_service.record_event('test-device-1', 'offline')

        stats = event_service.get_event_stats()

        assert 'total_events' in stats
        assert 'events_by_type' in stats
        assert 'active_alerts' in stats
        assert 'events_last_24h' in stats

        assert stats['total_events'] == 3
        assert stats['events_last_24h'] == 3

    def test_event_stats_with_alerts(self, event_service):
        """Test event stats includes alert count"""
        event_id = event_service.record_event('test-device-1', 'new_device')
        event_service.create_alert('test-device-1', event_id, 'new_device')

        stats = event_service.get_event_stats()
        assert stats['active_alerts'] == 1


class TestEventCleaning:
    """Tests for old event cleanup"""

    def test_clean_old_events(self, event_service, test_db):
        """Test cleaning up old events"""
        # Record an old event directly in the database
        old_date = (datetime.utcnow() - timedelta(days=100)).isoformat()

        with test_db.get_connection() as conn:
            conn.execute(
                """INSERT INTO device_events
                   (event_id, device_id, event_type, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid.uuid4()), 'test-device-1', 'online', old_date)
            )
            conn.commit()

        # Record a recent event
        event_service.record_event('test-device-1', 'online')

        # Clean events older than 90 days
        deleted = event_service.clean_old_events(days=90)

        assert deleted >= 1

        # Verify recent event still exists
        recent = event_service.get_events()
        assert len(recent) >= 1


class TestEventFiltering:
    """Tests for event filtering"""

    def test_filter_by_date_range(self, event_service, test_db):
        """Test filtering events by date range"""
        now = datetime.utcnow()
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()

        event_service.record_event('test-device-1', 'online')

        events = event_service.get_events(start_date=start, end_date=end)
        assert len(events) > 0

    def test_filter_no_results(self, event_service):
        """Test filtering with no results"""
        event_service.record_event('test-device-1', 'online')

        events = event_service.get_events(event_type='new_device')
        assert len(events) == 0
