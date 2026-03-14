"""
Retention Scheduler for HomeSentinel
Manages APScheduler-based cleanup tasks for events and alerts
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.retention_cleanup import RetentionCleanupService

logger = logging.getLogger(__name__)


class RetentionScheduler:
    """Manages background retention cleanup tasks"""

    def __init__(self, db, retention_days: int = 90, cleanup_hour: int = 2):
        """
        Initialize retention scheduler

        Args:
            db: Database connection
            retention_days: Number of days to retain events (default: 90)
            cleanup_hour: Hour (0-23) to run daily cleanup (default: 2 AM)
        """
        self.db = db
        self.retention_days = retention_days
        self.cleanup_hour = cleanup_hour
        self.cleanup_service = RetentionCleanupService(db, retention_days)
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.last_cleanup = None
        self.cleanup_stats = {}

    async def start(self) -> bool:
        """
        Start the retention scheduler

        Returns:
            True if scheduler started successfully
        """
        if self.is_running:
            logger.warning("Retention scheduler already running")
            return False

        try:
            self.scheduler = AsyncIOScheduler()

            # Schedule daily cleanup at specified hour, minute 0, second 0
            self.scheduler.add_job(
                self._cleanup_task,
                CronTrigger(hour=self.cleanup_hour, minute=0, second=0),
                id="retention_cleanup",
                name="Retention Cleanup Task",
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True

            logger.info(
                f"Retention scheduler started - daily cleanup at "
                f"{self.cleanup_hour:02d}:00:00 (retention: {self.retention_days} days)"
            )

            # Run initial cleanup on startup (optional, can be commented out)
            logger.info("Running initial retention cleanup on startup...")
            await self._cleanup_task()

            return True

        except Exception as e:
            logger.error(f"Failed to start retention scheduler: {e}")
            self.is_running = False
            return False

    async def stop(self) -> bool:
        """
        Stop the retention scheduler

        Returns:
            True if scheduler stopped successfully
        """
        if not self.is_running or not self.scheduler:
            return False

        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Retention scheduler stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping retention scheduler: {e}")
            return False

    async def _cleanup_task(self):
        """Execute the cleanup task (called by scheduler or manually)"""
        try:
            logger.info(f"Starting retention cleanup task at {datetime.now(timezone.utc).isoformat()}")

            # Run cleanup
            result = self.cleanup_service.cleanup_all(self.retention_days)

            # Update stats
            self.last_cleanup = datetime.now(timezone.utc).isoformat()
            self.cleanup_stats = result

            logger.info(
                f"Cleanup completed - "
                f"Events deleted: {result['events'].get('rows_deleted', 0)}, "
                f"Alerts deleted: {result['alerts'].get('rows_deleted', 0)}, "
                f"Total: {result.get('total_rows_deleted', 0)} rows"
            )

        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            self.cleanup_stats = {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

    def get_status(self) -> dict:
        """
        Get scheduler status

        Returns:
            Dictionary with scheduler status
        """
        return {
            "is_running": self.is_running,
            "retention_days": self.retention_days,
            "cleanup_hour": self.cleanup_hour,
            "last_cleanup": self.last_cleanup,
            "cleanup_stats": self.cleanup_stats
        }

    def get_retention_stats(self) -> dict:
        """
        Get current retention statistics

        Returns:
            Dictionary with retention stats
        """
        return self.cleanup_service.get_retention_stats()
