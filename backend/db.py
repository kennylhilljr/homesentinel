"""
Database module for HomeSentinel
Handles SQLite connection, migrations, and database operations
"""

import sqlite3
import os
import logging
import json
from typing import Optional, List
from contextlib import contextmanager
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "./backend/homesentinel.db")

# Get migrations path relative to this file
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_PATH = os.path.join(_SCRIPT_DIR, "migrations")


class Database:
    """Database connection and management class"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.connection = None
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _init_db(self):
        """Initialize database connection"""
        try:
            # Use check_same_thread=False for thread-safe operation with async
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
            logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Get a database connection context manager"""
        if self.connection is None:
            self._init_db()
        try:
            yield self.connection
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise

    def run_migrations(self):
        """Run all migrations in order"""
        try:
            # Create migrations table if it doesn't exist
            with self.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()

                # Get list of migration files
                if not os.path.exists(MIGRATIONS_PATH):
                    logger.warning(f"Migrations path does not exist: {MIGRATIONS_PATH}")
                    return

                migration_files = sorted([
                    f for f in os.listdir(MIGRATIONS_PATH)
                    if f.endswith('.sql')
                ])

                # Apply each migration
                for migration_file in migration_files:
                    # Check if migration already applied
                    cursor = conn.execute(
                        "SELECT * FROM migrations WHERE name = ?",
                        (migration_file,)
                    )
                    if cursor.fetchone():
                        logger.debug(f"Migration already applied: {migration_file}")
                        continue

                    # Read and execute migration
                    migration_path = os.path.join(MIGRATIONS_PATH, migration_file)
                    with open(migration_path, 'r') as f:
                        migration_sql = f.read()

                    # Execute migration
                    conn.executescript(migration_sql)
                    conn.commit()

                    # Record migration
                    conn.execute(
                        "INSERT INTO migrations (name) VALUES (?)",
                        (migration_file,)
                    )
                    conn.commit()
                    logger.info(f"Migration applied: {migration_file}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class NetworkDeviceRepository:
    """Repository for NetworkDevice operations"""

    def __init__(self, db: Database):
        self.db = db

    def create_or_update(self, device_id: str, mac_address: str,
                        current_ip: Optional[str] = None) -> dict:
        """Create or update a network device"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Check if device exists
                cursor.execute(
                    "SELECT device_id, current_ip, ip_history FROM network_devices WHERE device_id = ?",
                    (device_id,)
                )
                existing = cursor.fetchone()
                exists = existing is not None

                if exists:
                    # Update existing device
                    old_ip = existing[1]
                    ip_history_json = existing[2]

                    # Parse and update IP history if IP changed
                    ip_history = []
                    if ip_history_json:
                        try:
                            ip_history = json.loads(ip_history_json)
                        except (json.JSONDecodeError, TypeError):
                            ip_history = []

                    # Add old IP to history if it changed
                    if current_ip and old_ip and old_ip != current_ip:
                        ip_history.append({
                            'ip': old_ip,
                            'seen_at': datetime.utcnow().isoformat()
                        })

                    new_history_json = json.dumps(ip_history) if ip_history else None

                    cursor.execute("""
                        UPDATE network_devices
                        SET current_ip = ?, ip_history = ?, ip_history_updated_at = ?, last_seen = ?, status = ?, updated_at = ?
                        WHERE device_id = ?
                    """, (current_ip, new_history_json, datetime.utcnow(), datetime.utcnow(), 'online', datetime.utcnow(), device_id))
                else:
                    # Create new device
                    cursor.execute("""
                        INSERT INTO network_devices
                        (device_id, mac_address, current_ip, status, first_seen, last_seen, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (device_id, mac_address, current_ip, 'online',
                          datetime.utcnow(), datetime.utcnow(), datetime.utcnow(), datetime.utcnow()))

                conn.commit()

                # Return updated device
                return self.get_by_id(device_id)

        except sqlite3.Error as e:
            logger.error(f"Failed to create/update device: {e}")
            raise

    def get_by_id(self, device_id: str) -> Optional[dict]:
        """Get device by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM network_devices WHERE device_id = ?",
                    (device_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get device: {e}")
            raise

    def update_device_metadata(self, device_id: str, friendly_name: Optional[str] = None,
                               device_type: Optional[str] = None, vendor_name: Optional[str] = None,
                               notes: Optional[str] = None) -> Optional[dict]:
        """Update device metadata"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []

                if friendly_name is not None:
                    updates.append("friendly_name = ?")
                    params.append(friendly_name)
                if device_type is not None:
                    updates.append("device_type = ?")
                    params.append(device_type)
                if vendor_name is not None:
                    updates.append("vendor_name = ?")
                    params.append(vendor_name)
                if notes is not None:
                    updates.append("notes = ?")
                    params.append(notes)

                if not updates:
                    return self.get_by_id(device_id)

                updates.append("updated_at = ?")
                params.append(datetime.utcnow())
                params.append(device_id)

                cursor.execute(f"""
                    UPDATE network_devices
                    SET {', '.join(updates)}
                    WHERE device_id = ?
                """, params)
                conn.commit()
                return self.get_by_id(device_id)
        except sqlite3.Error as e:
            logger.error(f"Failed to update device metadata: {e}")
            raise

    def get_by_mac(self, mac_address: str) -> Optional[dict]:
        """Get device by MAC address"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM network_devices WHERE mac_address = ?",
                    (mac_address,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get device by MAC: {e}")
            raise

    def list_all(self) -> List[dict]:
        """List all devices"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM network_devices ORDER BY last_seen DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list devices: {e}")
            raise

    def list_by_status(self, status: str) -> List[dict]:
        """List devices by status"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM network_devices WHERE status = ? ORDER BY last_seen DESC",
                    (status,)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list devices by status: {e}")
            raise

    def mark_offline(self, device_id: str) -> Optional[dict]:
        """Mark device as offline"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE network_devices
                    SET status = ?, updated_at = ?
                    WHERE device_id = ?
                """, ('offline', datetime.utcnow(), device_id))
                conn.commit()
                return self.get_by_id(device_id)
        except sqlite3.Error as e:
            logger.error(f"Failed to mark device offline: {e}")
            raise

    def mark_online(self, device_id: str) -> Optional[dict]:
        """Mark device as online"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE network_devices
                    SET status = ?, last_seen = ?, updated_at = ?
                    WHERE device_id = ?
                """, ('online', datetime.utcnow(), datetime.utcnow(), device_id))
                conn.commit()
                return self.get_by_id(device_id)
        except sqlite3.Error as e:
            logger.error(f"Failed to mark device online: {e}")
            raise

    def delete(self, device_id: str) -> bool:
        """Delete a device"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM network_devices WHERE device_id = ?",
                    (device_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to delete device: {e}")
            raise


class PollingConfigRepository:
    """Repository for polling configuration"""

    def __init__(self, db: Database):
        self.db = db

    def get_config(self) -> dict:
        """Get polling configuration"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM polling_config WHERE id = 1")
                row = cursor.fetchone()
                if row:
                    return dict(row)
                else:
                    # Return defaults if not found
                    return {
                        'id': 1,
                        'polling_interval_seconds': 60,
                        'last_scan_timestamp': None
                    }
        except sqlite3.Error as e:
            logger.error(f"Failed to get polling config: {e}")
            raise

    def set_interval(self, interval_seconds: int) -> dict:
        """Set polling interval"""
        if interval_seconds <= 0:
            raise ValueError("Polling interval must be greater than 0")

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE polling_config
                    SET polling_interval_seconds = ?, updated_at = ?
                    WHERE id = 1
                """, (interval_seconds, datetime.utcnow()))
                conn.commit()
                return self.get_config()
        except sqlite3.Error as e:
            logger.error(f"Failed to set polling interval: {e}")
            raise

    def update_last_scan(self, timestamp: datetime) -> dict:
        """Update last scan timestamp"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE polling_config
                    SET last_scan_timestamp = ?, updated_at = ?
                    WHERE id = 1
                """, (timestamp, datetime.utcnow()))
                conn.commit()
                return self.get_config()
        except sqlite3.Error as e:
            logger.error(f"Failed to update last scan: {e}")
            raise


class DeviceGroupRepository:
    """Repository for device group operations"""

    def __init__(self, db: Database):
        self.db = db

    def create_group(self, group_id: str, name: str, color: str = '#3498db') -> dict:
        """Create a new device group"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO device_groups (group_id, name, color, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (group_id, name, color, datetime.utcnow(), datetime.utcnow()))
                conn.commit()
                return self.get_by_id(group_id)
        except sqlite3.Error as e:
            logger.error(f"Failed to create group: {e}")
            raise

    def get_by_id(self, group_id: str) -> Optional[dict]:
        """Get group by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM device_groups WHERE group_id = ?", (group_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get group: {e}")
            raise

    def get_by_name(self, name: str) -> Optional[dict]:
        """Get group by name"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM device_groups WHERE name = ?", (name,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get group by name: {e}")
            raise

    def list_all(self) -> List[dict]:
        """List all groups"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM device_groups ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list groups: {e}")
            raise

    def update_group(self, group_id: str, name: Optional[str] = None,
                     color: Optional[str] = None) -> Optional[dict]:
        """Update group metadata"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []

                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if color is not None:
                    updates.append("color = ?")
                    params.append(color)

                if not updates:
                    return self.get_by_id(group_id)

                updates.append("updated_at = ?")
                params.append(datetime.utcnow())
                params.append(group_id)

                cursor.execute(f"""
                    UPDATE device_groups
                    SET {', '.join(updates)}
                    WHERE group_id = ?
                """, params)
                conn.commit()
                return self.get_by_id(group_id)
        except sqlite3.Error as e:
            logger.error(f"Failed to update group: {e}")
            raise

    def delete_group(self, group_id: str) -> bool:
        """Delete a group"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM device_groups WHERE group_id = ?", (group_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to delete group: {e}")
            raise


class DeviceGroupMemberRepository:
    """Repository for device group membership"""

    def __init__(self, db: Database):
        self.db = db

    def add_member(self, group_id: str, device_id: str) -> bool:
        """Add device to group"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO device_group_members (group_id, device_id, created_at)
                    VALUES (?, ?, ?)
                """, (group_id, device_id, datetime.utcnow()))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to add group member: {e}")
            raise

    def remove_member(self, group_id: str, device_id: str) -> bool:
        """Remove device from group"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM device_group_members
                    WHERE group_id = ? AND device_id = ?
                """, (group_id, device_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to remove group member: {e}")
            raise

    def get_group_members(self, group_id: str) -> List[dict]:
        """Get all devices in a group"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.* FROM network_devices d
                    JOIN device_group_members m ON d.device_id = m.device_id
                    WHERE m.group_id = ?
                    ORDER BY d.last_seen DESC
                """, (group_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to get group members: {e}")
            raise

    def get_device_groups(self, device_id: str) -> List[dict]:
        """Get all groups a device belongs to"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT g.* FROM device_groups g
                    JOIN device_group_members m ON g.group_id = m.group_id
                    WHERE m.device_id = ?
                    ORDER BY g.created_at DESC
                """, (device_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to get device groups: {e}")
            raise

    def list_all_memberships(self) -> List[dict]:
        """List all group memberships"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM device_group_members ORDER BY group_id DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list memberships: {e}")
            raise


class DeviceEventRepository:
    """Repository for device events"""

    def __init__(self, db: Database):
        self.db = db

    def create(self, event_id: str, device_id: str, event_type: str,
               description: Optional[str] = None, metadata: Optional[str] = None) -> bool:
        """Create a new device event"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO device_events
                    (event_id, device_id, event_type, description, metadata, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (event_id, device_id, event_type, description, metadata))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to create event: {e}")
            raise

    def get_by_id(self, event_id: str) -> Optional[dict]:
        """Get event by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM device_events WHERE event_id = ?", (event_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get event: {e}")
            raise

    def list_by_device(self, device_id: str, limit: int = 100, offset: int = 0) -> List[dict]:
        """List events for a device"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM device_events
                    WHERE device_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (device_id, limit, offset))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list events by device: {e}")
            raise

    def list_all(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """List all events"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM device_events
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list events: {e}")
            raise

    def delete_older_than(self, days: int = 90) -> int:
        """Delete events older than specified days"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM device_events WHERE timestamp < ?", (cutoff_date,))
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Failed to delete old events: {e}")
            raise


class DeviceAlertRepository:
    """Repository for device alerts"""

    def __init__(self, db: Database):
        self.db = db

    def create(self, alert_id: str, device_id: str, event_id: str, alert_type: str) -> bool:
        """Create a new alert"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO device_alerts
                    (alert_id, device_id, event_id, alert_type, dismissed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (alert_id, device_id, event_id, alert_type))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to create alert: {e}")
            raise

    def get_by_id(self, alert_id: str) -> Optional[dict]:
        """Get alert by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM device_alerts WHERE alert_id = ?", (alert_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get alert: {e}")
            raise

    def list_active(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """List active (not dismissed) alerts"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM device_alerts
                    WHERE dismissed = 0
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list active alerts: {e}")
            raise

    def dismiss(self, alert_id: str) -> bool:
        """Dismiss an alert"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE device_alerts
                    SET dismissed = 1, dismissed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE alert_id = ?
                """, (alert_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to dismiss alert: {e}")
            raise

    def list_by_device(self, device_id: str, limit: int = 50, offset: int = 0) -> List[dict]:
        """List alerts for a device"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM device_alerts
                    WHERE device_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (device_id, limit, offset))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list alerts by device: {e}")
            raise
