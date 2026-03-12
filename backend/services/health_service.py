"""
Network Health Score Service for HomeSentinel
2026-03-12: Computes a 0-100 composite network health score for gamification.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from db import Database

logger = logging.getLogger(__name__)


class NetworkHealthService:
    """Computes a composite network health score from device, speed, and signal data."""

    def __init__(self, db: Database):
        self.db = db

    def compute_health_score(self) -> Dict[str, Any]:
        """
        Compute a 0-100 health score with breakdown.

        Components:
          - Device online ratio (30 pts)
          - Speed vs 100 Mbps baseline (25 pts)
          - Signal quality RSRP (15 pts)
          - Uptime streak (15 pts)
          - Stability — fewer offline events in 24h (15 pts)

        Returns:
            Dict with score, breakdown, streak, records, and fun facts.
        """
        try:
            with self.db.get_connection() as conn:
                # --- Device online ratio (30 pts) ---
                total = conn.execute("SELECT COUNT(*) FROM network_devices").fetchone()[0]
                online = conn.execute(
                    "SELECT COUNT(*) FROM network_devices WHERE status = 'online'"
                ).fetchone()[0]
                device_ratio = (online / total) if total > 0 else 0
                device_score = round(device_ratio * 30, 1)

                # --- Speed vs baseline (25 pts) ---
                speed_row = conn.execute(
                    """SELECT AVG(download_mbps) FROM speed_tests
                       WHERE error IS NULL
                         AND timestamp >= datetime('now', '-24 hours')"""
                ).fetchone()
                avg_download = speed_row[0] if speed_row and speed_row[0] else 0
                speed_baseline = 100.0  # Mbps
                speed_ratio = min(avg_download / speed_baseline, 1.0)
                speed_score = round(speed_ratio * 25, 1)

                # --- Signal quality RSRP (15 pts) ---
                # Linear: -120 dBm = 0, -80 dBm = 15
                rsrp_row = conn.execute(
                    """SELECT cellular_rsrp FROM speed_tests
                       WHERE cellular_rsrp IS NOT NULL
                       ORDER BY timestamp DESC LIMIT 1"""
                ).fetchone()
                rsrp = rsrp_row[0] if rsrp_row else -120
                signal_ratio = max(0, min(1, (rsrp + 120) / 40))
                signal_score = round(signal_ratio * 15, 1)

                # --- Uptime streak (15 pts) ---
                streak = self._compute_uptime_streak(conn, total)
                streak_score = round(min(streak / 30, 1.0) * 15, 1)

                # --- Stability (15 pts) ---
                offline_24h = conn.execute(
                    """SELECT COUNT(*) FROM device_events
                       WHERE event_type IN ('offline', 'disconnected')
                         AND timestamp >= datetime('now', '-24 hours')"""
                ).fetchone()[0]
                stability_ratio = max(0, 1 - offline_24h / 20)
                stability_score = round(stability_ratio * 15, 1)

                # Total
                total_score = round(
                    device_score + speed_score + signal_score + streak_score + stability_score
                )

                # Fun facts
                speed_record = conn.execute(
                    "SELECT MAX(download_mbps) FROM speed_tests WHERE error IS NULL"
                ).fetchone()
                speed_record_mbps = round(speed_record[0], 1) if speed_record and speed_record[0] else 0

                devices_ever = conn.execute(
                    "SELECT COUNT(*) FROM network_devices"
                ).fetchone()[0]

            return {
                "score": total_score,
                "breakdown": {
                    "devices": {"score": device_score, "max": 30, "detail": f"{online}/{total} online"},
                    "speed": {"score": speed_score, "max": 25, "detail": f"{round(avg_download, 1)} Mbps avg"},
                    "signal": {"score": signal_score, "max": 15, "detail": f"{rsrp} dBm RSRP"},
                    "uptime": {"score": streak_score, "max": 15, "detail": f"{streak} day streak"},
                    "stability": {"score": stability_score, "max": 15, "detail": f"{offline_24h} offline events (24h)"},
                },
                "streak_days": streak,
                "speed_record_mbps": speed_record_mbps,
                "devices_ever_seen": devices_ever,
            }

        except Exception as e:
            logger.error(f"Failed to compute health score: {e}")
            raise

    def _compute_uptime_streak(self, conn, total_devices: int) -> int:
        """Count consecutive days (backwards from today) with <10% device offline events."""
        if total_devices == 0:
            return 0

        threshold = max(1, total_devices * 0.1)
        streak = 0

        for days_ago in range(0, 365):
            date = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            day_start = f"{date}T00:00:00"
            day_end = f"{date}T23:59:59"

            offline_count = conn.execute(
                """SELECT COUNT(*) FROM device_events
                   WHERE event_type IN ('offline', 'disconnected')
                     AND timestamp >= ? AND timestamp <= ?""",
                (day_start, day_end)
            ).fetchone()[0]

            if offline_count >= threshold:
                break
            streak += 1

        return streak
