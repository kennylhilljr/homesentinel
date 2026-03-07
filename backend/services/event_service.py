"""
Event Service for HomeSentinel
Handles device event tracking and alert generation
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from db import Database

logger = logging.getLogger(__name__)


class EventService:
    """Service for managing device events and alerts"""

    def __init__(self, db: Database):
        """Initialize EventService with database connection"""
        self.db = db

    def record_event(
        self,
        device_id: str,
        event_type: str,
        description: str = None,
        metadata: str = None
    ) -> str:
        """
        Record a device event

        Args:
            device_id: ID of the device
            event_type: Type of event (connected, disconnected, online, offline, new_device)
            description: Optional description of the event
            metadata: Optional JSON metadata

        Returns:
            event_id: UUID of the created event
        """
        try:
            event_id = str(uuid.uuid4())

            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO device_events
                    (event_id, device_id, event_type, description, metadata, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (event_id, device_id, event_type, description, metadata)
                )
                conn.commit()

            logger.info(f"Event recorded: {event_id} - {event_type} for device {device_id}")
            return event_id

        except Exception as e:
            logger.error(f"Failed to record event: {e}")
            raise

    def get_events(
        self,
        device_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve events with optional filtering

        Args:
            device_id: Optional filter by device
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            event_type: Optional filter by event type
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of event dictionaries
        """
        try:
            query = "SELECT * FROM device_events WHERE 1=1"
            params = []

            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            with self.db.get_connection() as conn:
                cursor = conn.execute(query, params)
                events = []
                for row in cursor.fetchall():
                    events.append({
                        "event_id": row[0],
                        "device_id": row[1],
                        "event_type": row[2],
                        "timestamp": row[3],
                        "description": row[4],
                        "metadata": row[5],
                        "created_at": row[6]
                    })

            return events

        except Exception as e:
            logger.error(f"Failed to retrieve events: {e}")
            raise

    def get_event_count(
        self,
        device_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> int:
        """
        Get count of events matching criteria

        Args:
            device_id: Optional filter by device
            start_date: Optional start date
            end_date: Optional end date
            event_type: Optional filter by event type

        Returns:
            Count of matching events
        """
        try:
            query = "SELECT COUNT(*) FROM device_events WHERE 1=1"
            params = []

            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)

            with self.db.get_connection() as conn:
                cursor = conn.execute(query, params)
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Failed to get event count: {e}")
            raise

    def create_alert(
        self,
        device_id: str,
        event_id: str,
        alert_type: str
    ) -> str:
        """
        Create an alert for a device event

        Args:
            device_id: ID of the device
            event_id: ID of the event
            alert_type: Type of alert (new_device, device_reconnected, device_offline)

        Returns:
            alert_id: UUID of the created alert
        """
        try:
            alert_id = str(uuid.uuid4())

            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO device_alerts
                    (alert_id, device_id, event_id, alert_type, dismissed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (alert_id, device_id, event_id, alert_type)
                )
                conn.commit()

            logger.info(f"Alert created: {alert_id} - {alert_type} for device {device_id}")
            return alert_id

        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            raise

    def get_alerts(
        self,
        dismissed: bool = False,
        device_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve alerts with optional filtering

        Args:
            dismissed: Filter by dismissed status
            device_id: Optional filter by device
            limit: Maximum number of alerts to return
            offset: Number of alerts to skip

        Returns:
            List of alert dictionaries
        """
        try:
            query = "SELECT * FROM device_alerts WHERE dismissed = ?"
            params = [1 if dismissed else 0]

            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            with self.db.get_connection() as conn:
                cursor = conn.execute(query, params)
                alerts = []
                for row in cursor.fetchall():
                    alerts.append({
                        "alert_id": row[0],
                        "device_id": row[1],
                        "event_id": row[2],
                        "alert_type": row[3],
                        "dismissed": bool(row[4]),
                        "dismissed_at": row[5],
                        "created_at": row[6],
                        "updated_at": row[7]
                    })

            return alerts

        except Exception as e:
            logger.error(f"Failed to retrieve alerts: {e}")
            raise

    def dismiss_alert(self, alert_id: str) -> bool:
        """
        Dismiss an alert

        Args:
            alert_id: ID of the alert to dismiss

        Returns:
            True if successful
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE device_alerts
                    SET dismissed = 1, dismissed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE alert_id = ?
                    """,
                    (alert_id,)
                )
                conn.commit()

            logger.info(f"Alert dismissed: {alert_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to dismiss alert: {e}")
            raise

    def detect_new_device(self, device_id: str) -> bool:
        """
        Check if a device is newly discovered (first time seen)

        Args:
            device_id: ID of the device

        Returns:
            True if device is new (no prior events)
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM device_events WHERE device_id = ?",
                    (device_id,)
                )
                count = cursor.fetchone()[0]
                return count == 0

        except Exception as e:
            logger.error(f"Failed to detect new device: {e}")
            raise

    def get_event_stats(self) -> Dict[str, Any]:
        """
        Get event statistics

        Returns:
            Dictionary with event statistics
        """
        try:
            with self.db.get_connection() as conn:
                # Total events
                total = conn.execute(
                    "SELECT COUNT(*) FROM device_events"
                ).fetchone()[0]

                # Events by type
                cursor = conn.execute(
                    """
                    SELECT event_type, COUNT(*) as count
                    FROM device_events
                    GROUP BY event_type
                    """
                )
                events_by_type = {row[0]: row[1] for row in cursor.fetchall()}

                # Active alerts
                active_alerts = conn.execute(
                    "SELECT COUNT(*) FROM device_alerts WHERE dismissed = 0"
                ).fetchone()[0]

                # Last 24 hours events
                last_24h = conn.execute(
                    """
                    SELECT COUNT(*) FROM device_events
                    WHERE timestamp >= datetime('now', '-1 day')
                    """
                ).fetchone()[0]

                return {
                    "total_events": total,
                    "events_by_type": events_by_type,
                    "active_alerts": active_alerts,
                    "events_last_24h": last_24h
                }

        except Exception as e:
            logger.error(f"Failed to get event stats: {e}")
            raise

    def clean_old_events(self, days: int = 90) -> int:
        """
        Clean up events older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted events
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM device_events WHERE timestamp < ?",
                    (cutoff_date,)
                )
                conn.commit()
                deleted = cursor.rowcount

            logger.info(f"Cleaned up {deleted} events older than {days} days")
            return deleted

        except Exception as e:
            logger.error(f"Failed to clean old events: {e}")
            raise
