"""
Retention Cleanup Service for HomeSentinel
Handles automatic cleanup of old events and alerts
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from db import Database

logger = logging.getLogger(__name__)


class RetentionCleanupService:
    """Service for managing data retention and cleanup"""

    def __init__(self, db: Database, retention_days: int = 90):
        """
        Initialize retention cleanup service

        Args:
            db: Database connection
            retention_days: Number of days to retain events (default: 90)
        """
        self.db = db
        self.retention_days = retention_days

    def cleanup_old_events(self, days: int = None) -> Dict[str, Any]:
        """
        Delete events older than specified days

        Args:
            days: Number of days to retain (uses default if not specified)

        Returns:
            Dictionary with cleanup results
        """
        if days is None:
            days = self.retention_days

        try:
            from datetime import timedelta
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            with self.db.write_connection() as conn:
                cursor = conn.cursor()

                # Get count before deletion
                cursor.execute(
                    "SELECT COUNT(*) FROM device_events WHERE timestamp < ?",
                    (cutoff_date,)
                )
                count_before = cursor.fetchone()[0]

                # Delete old events
                cursor.execute(
                    "DELETE FROM device_events WHERE timestamp < ?",
                    (cutoff_date,)
                )
                conn.commit()
                rows_deleted = cursor.rowcount

                logger.info(
                    f"Cleanup: Deleted {rows_deleted} events older than {days} days "
                    f"(before: {count_before}, cutoff: {cutoff_date})"
                )

                return {
                    "success": True,
                    "rows_deleted": rows_deleted,
                    "cutoff_date": cutoff_date,
                    "retention_days": days,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def cleanup_old_alerts(self, days: int = None) -> Dict[str, Any]:
        """
        Delete dismissed alerts older than specified days

        Args:
            days: Number of days to retain (uses default if not specified)

        Returns:
            Dictionary with cleanup results
        """
        if days is None:
            days = self.retention_days

        try:
            from datetime import timedelta
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            with self.db.write_connection() as conn:
                cursor = conn.cursor()

                # Get count before deletion
                cursor.execute(
                    "SELECT COUNT(*) FROM device_alerts WHERE dismissed = 1 AND dismissed_at < ?",
                    (cutoff_date,)
                )
                count_before = cursor.fetchone()[0]

                # Delete old dismissed alerts
                cursor.execute(
                    "DELETE FROM device_alerts WHERE dismissed = 1 AND dismissed_at < ?",
                    (cutoff_date,)
                )
                conn.commit()
                rows_deleted = cursor.rowcount

                logger.info(
                    f"Cleanup: Deleted {rows_deleted} dismissed alerts older than {days} days "
                    f"(before: {count_before}, cutoff: {cutoff_date})"
                )

                return {
                    "success": True,
                    "rows_deleted": rows_deleted,
                    "cutoff_date": cutoff_date,
                    "retention_days": days,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to cleanup old alerts: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def cleanup_all(self, days: int = None) -> Dict[str, Any]:
        """
        Run complete cleanup (events + dismissed alerts)

        Args:
            days: Number of days to retain (uses default if not specified)

        Returns:
            Dictionary with combined cleanup results
        """
        if days is None:
            days = self.retention_days

        events_result = self.cleanup_old_events(days)
        alerts_result = self.cleanup_old_alerts(days)

        return {
            "events": events_result,
            "alerts": alerts_result,
            "total_rows_deleted": (
                events_result.get("rows_deleted", 0) +
                alerts_result.get("rows_deleted", 0)
            ),
            "retention_days": days,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_retention_stats(self) -> Dict[str, Any]:
        """
        Get retention statistics

        Returns:
            Dictionary with event and alert counts
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Count all events
                cursor.execute("SELECT COUNT(*) FROM device_events")
                total_events = cursor.fetchone()[0]

                # Count events older than retention period
                from datetime import timedelta
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
                cursor.execute(
                    "SELECT COUNT(*) FROM device_events WHERE timestamp < ?",
                    (cutoff_date,)
                )
                old_events = cursor.fetchone()[0]

                # Count alerts
                cursor.execute("SELECT COUNT(*) FROM device_alerts WHERE dismissed = 0")
                active_alerts = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM device_alerts WHERE dismissed = 1")
                dismissed_alerts = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM device_alerts WHERE dismissed = 1 AND dismissed_at < ?",
                    (cutoff_date,)
                )
                old_dismissed_alerts = cursor.fetchone()[0]

                return {
                    "total_events": total_events,
                    "events_to_cleanup": old_events,
                    "active_alerts": active_alerts,
                    "dismissed_alerts": dismissed_alerts,
                    "dismissed_alerts_to_cleanup": old_dismissed_alerts,
                    "retention_days": self.retention_days,
                    "cutoff_date": cutoff_date,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get retention stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
