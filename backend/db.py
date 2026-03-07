"""
Database module for HomeSentinel
Handles SQLite connection, migrations, and database operations
"""

import sqlite3
import os
import logging
from typing import Optional, List
from contextlib import contextmanager
from datetime import datetime

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
                    "SELECT device_id FROM network_devices WHERE device_id = ?",
                    (device_id,)
                )
                exists = cursor.fetchone() is not None

                if exists:
                    # Update existing device
                    cursor.execute("""
                        UPDATE network_devices
                        SET current_ip = ?, last_seen = ?, status = ?, updated_at = ?
                        WHERE device_id = ?
                    """, (current_ip, datetime.utcnow(), 'online', datetime.utcnow(), device_id))
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
