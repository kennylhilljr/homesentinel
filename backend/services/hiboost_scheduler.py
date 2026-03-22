"""
HiBoost RF parameter polling scheduler.

Polls the HiBoost cloud API every 5 minutes and stores RF params
in the hiboost_history table for historical charting.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 300  # 5 minutes


class HiBoostScheduler:
    """Periodically polls HiBoost RF data and stores in the database."""

    def __init__(self, hiboost_service, db, interval: int = DEFAULT_INTERVAL):
        self.service = hiboost_service
        self.db = db
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"HiBoost scheduler started (interval: {self.interval}s)")

    async def stop(self):
        """Stop the polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HiBoost scheduler stopped")

    async def _poll_loop(self):
        # Initial poll after short delay to let startup finish
        await asyncio.sleep(10)
        while self._running:
            try:
                self._record_snapshot()
            except Exception as e:
                logger.error(f"HiBoost poll failed: {e}")
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

    def _record_snapshot(self):
        """Poll current RF params and insert into hiboost_history."""
        devices = self.service.get_device_list()
        if not devices:
            return

        for device in devices:
            device_id = device.get("id")
            if not device_id:
                continue

            try:
                self.service.clear_cache()
                rf = self.service.get_rf_params(device_id)
            except Exception as e:
                logger.warning(f"Failed to get RF params for {device_id}: {e}")
                continue

            temp = rf.get("temperature")
            now = datetime.now(timezone.utc).isoformat()

            with self.db.write_connection() as conn:
                cursor = conn.cursor()
                for band in rf.get("bands", []):
                    cursor.execute(
                        """INSERT INTO hiboost_history
                           (device_id, band, output_power_dl, output_power_ul,
                            gain_dl, gain_ul, mgc_dl, mgc_ul,
                            rf_switch, rf_status, iso_dl, iso_ul,
                            overload_dl, overload_ul, temperature, timestamp)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            device_id,
                            band["name"],
                            band.get("output_power_dl"),
                            band.get("output_power_ul"),
                            band.get("gain_dl"),
                            band.get("gain_ul"),
                            band.get("mgc_dl", 0),
                            band.get("mgc_ul", 0),
                            1 if band.get("rf_switch") else 0,
                            1 if band.get("rf_status") else 0,
                            1 if band.get("iso_dl") else 0,
                            1 if band.get("iso_ul") else 0,
                            1 if band.get("overload_dl") else 0,
                            1 if band.get("overload_ul") else 0,
                            temp,
                            now,
                        ),
                    )
                conn.commit()

            logger.debug(f"HiBoost snapshot recorded for {device_id} ({len(rf.get('bands', []))} bands)")

    def poll_now(self):
        """Manually trigger a poll (synchronous)."""
        self._record_snapshot()
