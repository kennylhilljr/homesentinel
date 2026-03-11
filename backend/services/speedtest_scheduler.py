"""
Speed Test Scheduler for HomeSentinel.

2026-03-11: Background job that runs Ookla speedtest on the Chester 5G router
every 30 minutes via SSH. Follows the same asyncio pattern as BackgroundPoller.
After each test, generates statistical insights from accumulated data.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 2026-03-11: Default 30-minute interval, staggered from the 60s ARP scan
DEFAULT_SPEEDTEST_INTERVAL = 1800  # 30 minutes in seconds


class SpeedTestScheduler:
    """Background scheduler that runs speed tests at a configurable interval."""

    def __init__(self, speedtest_service, interval_seconds: int = DEFAULT_SPEEDTEST_INTERVAL):
        self.speedtest_service = speedtest_service
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.last_test_time: Optional[datetime] = None
        self.test_count = 0
        self.last_error: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    def set_interval(self, interval_seconds: int):
        """Update the test interval (minimum 60 seconds)."""
        if interval_seconds < 60:
            raise ValueError("Speed test interval must be at least 60 seconds")
        self.interval_seconds = interval_seconds
        logger.info(f"Speed test interval updated to {interval_seconds}s")

    async def start(self):
        """Start the background speed test loop."""
        if self.is_running:
            logger.warning("Speed test scheduler already running")
            return

        self.is_running = True
        logger.info(f"Starting speed test scheduler (interval: {self.interval_seconds}s)")
        self._task = asyncio.create_task(self._test_loop())

    async def stop(self):
        """Stop the background speed test loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Speed test scheduler stopped")

    async def _test_loop(self):
        """Main loop: run speedtest, generate insights, sleep, repeat."""
        # 2026-03-11: Initial delay of 60s to let other services start up
        await asyncio.sleep(60)

        while self.is_running:
            try:
                await self._run_test()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                logger.debug("Speed test loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in speed test loop: {e}")
                self.last_error = str(e)
                await asyncio.sleep(min(self.interval_seconds, 60))

    async def _run_test(self):
        """Run a single speed test in a thread executor (blocking SSH call)."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self.speedtest_service.run_speedtest
            )

            self.last_test_time = datetime.utcnow()
            self.test_count += 1

            if result.get("error"):
                self.last_error = result["error"]
                logger.warning(f"Speed test #{self.test_count} error: {result['error']}")
            else:
                self.last_error = None
                logger.info(
                    f"Speed test #{self.test_count}: "
                    f"↓{result['download_mbps']} Mbps ↑{result['upload_mbps']} Mbps"
                )

                # Generate insights after successful test
                try:
                    await loop.run_in_executor(
                        None, self.speedtest_service.generate_insights
                    )
                except Exception as e:
                    logger.warning(f"Insight generation failed: {e}")

        except Exception as e:
            logger.error(f"Speed test execution failed: {e}")
            self.last_error = str(e)

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_test_time": self.last_test_time.isoformat() if self.last_test_time else None,
            "test_count": self.test_count,
            "last_error": self.last_error,
        }
