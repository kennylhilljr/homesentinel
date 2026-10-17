"""
Daily Digest Service for HomeSentinel
2026-03-12: Computes daily summary statistics for the dashboard digest card.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from db import Database

logger = logging.getLogger(__name__)


class DigestService:
    """Computes daily digest summaries from device events and speed tests."""

    def __init__(self, db: Database):
        self.db = db

    def compute_daily_digest(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute a digest for a single day.

        Args:
            date: ISO date string (YYYY-MM-DD). Defaults to yesterday.

        Returns:
            Dict with summary statistics.
        """
        if date is None:
            date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        day_start = f"{date}T00:00:00"
        day_end = f"{date}T23:59:59"

        try:
            with self.db.get_connection() as conn:
                # Device counts — current snapshot
                total_devices = conn.execute(
                    "SELECT COUNT(*) FROM network_devices"
                ).fetchone()[0]

                online_devices = conn.execute(
                    "SELECT COUNT(*) FROM network_devices WHERE status = 'online'"
                ).fetchone()[0]

                # New devices discovered that day
                new_device_rows = conn.execute(
                    """SELECT nd.friendly_name, nd.mac_address
                       FROM device_events de
                       JOIN network_devices nd ON nd.device_id = de.device_id
                       WHERE de.event_type = 'new_device'
                         AND de.timestamp >= ? AND de.timestamp <= ?""",
                    (day_start, day_end)
                ).fetchall()
                new_devices = [
                    {"name": r[0] or r[1], "mac": r[1]} for r in new_device_rows
                ]

                # Offline events that day
                offline_events = conn.execute(
                    """SELECT COUNT(*) FROM device_events
                       WHERE event_type IN ('offline', 'disconnected')
                         AND timestamp >= ? AND timestamp <= ?""",
                    (day_start, day_end)
                ).fetchone()[0]

                # Speed test stats for the day
                speed_row = conn.execute(
                    """SELECT AVG(download_mbps), MAX(download_mbps), MIN(download_mbps),
                              AVG(upload_mbps), AVG(ping_ms), COUNT(*)
                       FROM speed_tests
                       WHERE error IS NULL
                         AND timestamp >= ? AND timestamp <= ?""",
                    (day_start, day_end)
                ).fetchone()

                speed_stats = None
                if speed_row and speed_row[5] > 0:
                    speed_stats = {
                        "avg_download": round(speed_row[0], 1),
                        "max_download": round(speed_row[1], 1),
                        "min_download": round(speed_row[2], 1),
                        "avg_upload": round(speed_row[3], 1),
                        "avg_ping": round(speed_row[4], 1),
                        "test_count": speed_row[5],
                    }

                # Average signal strength (RSRP) for the day
                signal_row = conn.execute(
                    """SELECT AVG(cellular_rsrp)
                       FROM speed_tests
                       WHERE cellular_rsrp IS NOT NULL
                         AND timestamp >= ? AND timestamp <= ?""",
                    (day_start, day_end)
                ).fetchone()
                avg_rsrp = round(signal_row[0], 1) if signal_row and signal_row[0] else None

            return {
                "date": date,
                "total_devices": total_devices,
                "online_devices": online_devices,
                "new_devices_count": len(new_devices),
                "new_devices": new_devices,
                "offline_events": offline_events,
                "speed": speed_stats,
                "avg_signal_rsrp": avg_rsrp,
            }

        except Exception as e:
            logger.error(f"Failed to compute daily digest: {e}")
            raise
