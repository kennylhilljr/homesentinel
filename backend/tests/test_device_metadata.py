"""
Tests for Device Metadata and Device Groups
"""

import pytest
import os
import sys
import tempfile
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Database, NetworkDeviceRepository, DeviceGroupRepository, DeviceGroupMemberRepository
from services.device_scanner import NetworkDeviceService


class TestDeviceMetadata:
    """Tests for device metadata functionality"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()
        yield db
        db.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def device_repo(self, temp_db):
        """Create device repository"""
        return NetworkDeviceRepository(temp_db)

    @pytest.fixture
    def group_repo(self, temp_db):
        """Create group repository"""
        return DeviceGroupRepository(temp_db)

    @pytest.fixture
    def member_repo(self, temp_db):
        """Create member repository"""
        return DeviceGroupMemberRepository(temp_db)

    @pytest.fixture
    def device_service(self, temp_db):
        """Create device service"""
        return NetworkDeviceService(temp_db)

    @pytest.fixture
    def sample_device(self, device_repo):
        """Create a sample device"""
        return device_repo.create_or_update(
            "test-device-1",
            "00:11:22:33:44:55",
            "192.168.1.100"
        )

    def test_update_device_friendly_name(self, device_service, sample_device):
        """Test updating device friendly name"""
        device_id = sample_device['device_id']
        updated = device_service.update_device_friendly_name(
            device_id,
            "Living Room TV"
        )

        assert updated['friendly_name'] == "Living Room TV"

    def test_update_device_type(self, device_service, sample_device):
        """Test updating device type"""
        device_id = sample_device['device_id']
        updated = device_service.update_device_type(device_id, "tv")

        assert updated['device_type'] == "tv"

    def test_update_device_vendor(self, device_service, sample_device):
        """Test updating device vendor"""
        device_id = sample_device['device_id']
        updated = device_service.update_device_vendor(device_id, "Apple Inc.")

        assert updated['vendor_name'] == "Apple Inc."

    def test_set_device_notes(self, device_service, sample_device):
        """Test setting device notes"""
        device_id = sample_device['device_id']
        notes = "Primary living room device"
        updated = device_service.set_device_notes(device_id, notes)

        assert updated['notes'] == notes

    def test_update_multiple_fields(self, device_repo, sample_device):
        """Test updating multiple device fields"""
        device_id = sample_device['device_id']
        updated = device_repo.update_device_metadata(
            device_id,
            friendly_name="My Device",
            device_type="computer",
            vendor_name="Intel",
            notes="Test device"
        )

        assert updated['friendly_name'] == "My Device"
        assert updated['device_type'] == "computer"
        assert updated['vendor_name'] == "Intel"
        assert updated['notes'] == "Test device"

    def test_create_device_with_vendor(self, device_service):
        """Test creating device with OUI vendor lookup"""
        # Use Apple OUI prefix
        device = device_service.create_device_with_vendor("001A2B:DD:EE:FF", "192.168.1.100")

        assert device['vendor_name'] == "Apple Inc."

    def test_lookup_vendor_by_mac(self, device_service):
        """Test vendor lookup by MAC"""
        vendor = device_service.lookup_vendor_by_mac("001A2B:DD:EE:FF")
        assert vendor == "Apple Inc."

    def test_device_metadata_persistence(self, device_repo, sample_device):
        """Test that device metadata persists"""
        device_id = sample_device['device_id']

        # Update metadata
        device_repo.update_device_metadata(
            device_id,
            friendly_name="Kitchen Device",
            device_type="iot"
        )

        # Retrieve and verify
        retrieved = device_repo.get_by_id(device_id)
        assert retrieved['friendly_name'] == "Kitchen Device"
        assert retrieved['device_type'] == "iot"

    def test_device_default_type(self, sample_device):
        """Test that device type defaults to 'unknown'"""
        assert sample_device['device_type'] == "unknown"

    def test_device_vendor_initially_null(self, sample_device):
        """Test that vendor_name is initially null"""
        assert sample_device['vendor_name'] is None

    def test_device_friendly_name_initially_null(self, sample_device):
        """Test that friendly_name is initially null"""
        assert sample_device['friendly_name'] is None

    def test_device_notes_initially_null(self, sample_device):
        """Test that notes is initially null"""
        assert sample_device['notes'] is None


class TestDeviceGroups:
    """Tests for device groups functionality"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        db.run_migrations()
        yield db
        db.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def device_repo(self, temp_db):
        """Create device repository"""
        return NetworkDeviceRepository(temp_db)

    @pytest.fixture
    def group_repo(self, temp_db):
        """Create group repository"""
        return DeviceGroupRepository(temp_db)

    @pytest.fixture
    def member_repo(self, temp_db):
        """Create member repository"""
        return DeviceGroupMemberRepository(temp_db)

    @pytest.fixture
    def sample_devices(self, device_repo):
        """Create sample devices"""
        devices = []
        for i in range(3):
            device = device_repo.create_or_update(
                f"test-device-{i}",
                f"00:11:22:33:44:{i:02x}",
                f"192.168.1.{100 + i}"
            )
            devices.append(device)
        return devices

    @pytest.fixture
    def sample_group(self, group_repo):
        """Create a sample group"""
        group_id = str(uuid.uuid4())
        return group_repo.create_group(group_id, "Living Room", "#3498db")

    def test_create_device_group(self, group_repo):
        """Test creating a device group"""
        group_id = str(uuid.uuid4())
        group = group_repo.create_group(group_id, "Bedroom", "#e74c3c")

        assert group['group_id'] == group_id
        assert group['name'] == "Bedroom"
        assert group['color'] == "#e74c3c"

    def test_create_group_default_color(self, group_repo):
        """Test creating a group with default color"""
        group_id = str(uuid.uuid4())
        group = group_repo.create_group(group_id, "Kitchen")

        assert group['color'] == "#3498db"

    def test_get_group_by_id(self, group_repo, sample_group):
        """Test retrieving group by ID"""
        retrieved = group_repo.get_by_id(sample_group['group_id'])

        assert retrieved['group_id'] == sample_group['group_id']
        assert retrieved['name'] == "Living Room"

    def test_get_group_by_name(self, group_repo, sample_group):
        """Test retrieving group by name"""
        retrieved = group_repo.get_by_name("Living Room")

        assert retrieved['group_id'] == sample_group['group_id']

    def test_list_all_groups(self, group_repo):
        """Test listing all groups"""
        for i in range(3):
            group_repo.create_group(str(uuid.uuid4()), f"Group {i}")

        groups = group_repo.list_all()
        assert len(groups) >= 3

    def test_update_group_name(self, group_repo, sample_group):
        """Test updating group name"""
        updated = group_repo.update_group(
            sample_group['group_id'],
            name="Master Bedroom"
        )

        assert updated['name'] == "Master Bedroom"

    def test_update_group_color(self, group_repo, sample_group):
        """Test updating group color"""
        updated = group_repo.update_group(
            sample_group['group_id'],
            color="#2ecc71"
        )

        assert updated['color'] == "#2ecc71"

    def test_delete_group(self, group_repo, sample_group):
        """Test deleting a group"""
        success = group_repo.delete_group(sample_group['group_id'])

        assert success is True
        assert group_repo.get_by_id(sample_group['group_id']) is None

    def test_add_device_to_group(self, member_repo, sample_group, sample_devices):
        """Test adding device to group"""
        device_id = sample_devices[0]['device_id']
        success = member_repo.add_member(sample_group['group_id'], device_id)

        assert success is True

    def test_remove_device_from_group(self, member_repo, sample_group, sample_devices):
        """Test removing device from group"""
        group_id = sample_group['group_id']
        device_id = sample_devices[0]['device_id']

        member_repo.add_member(group_id, device_id)
        success = member_repo.remove_member(group_id, device_id)

        assert success is True

    def test_get_group_members(self, member_repo, sample_group, sample_devices):
        """Test getting group members"""
        group_id = sample_group['group_id']

        # Add some devices
        for device in sample_devices[:2]:
            member_repo.add_member(group_id, device['device_id'])

        members = member_repo.get_group_members(group_id)
        assert len(members) == 2

    def test_get_device_groups(self, member_repo, sample_group, sample_devices):
        """Test getting groups for a device"""
        device_id = sample_devices[0]['device_id']
        group_id = sample_group['group_id']

        member_repo.add_member(group_id, device_id)

        groups = member_repo.get_device_groups(device_id)
        assert len(groups) >= 1
        assert groups[0]['group_id'] == group_id

    def test_device_group_membership_persistence(self, member_repo, sample_group, sample_devices):
        """Test that group memberships persist"""
        group_id = sample_group['group_id']
        device_id = sample_devices[0]['device_id']

        member_repo.add_member(group_id, device_id)

        # Verify persistence
        members = member_repo.get_group_members(group_id)
        member_ids = [m['device_id'] for m in members]
        assert device_id in member_ids

    def test_add_same_device_twice(self, member_repo, sample_group, sample_devices):
        """Test adding same device twice (should be idempotent)"""
        group_id = sample_group['group_id']
        device_id = sample_devices[0]['device_id']

        member_repo.add_member(group_id, device_id)
        member_repo.add_member(group_id, device_id)

        members = member_repo.get_group_members(group_id)
        assert len(members) == 1

    def test_list_all_memberships(self, member_repo, sample_group, sample_devices):
        """Test listing all memberships"""
        group_id = sample_group['group_id']

        # Add multiple devices
        for device in sample_devices:
            member_repo.add_member(group_id, device['device_id'])

        memberships = member_repo.list_all_memberships()
        assert len(memberships) >= 3
