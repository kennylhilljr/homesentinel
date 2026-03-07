"""
Background Polling Service for HomeSentinel
Implements periodic ARP scanning and device updates
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import os

logger = logging.getLogger(__name__)


class BackgroundPoller:
    """Background polling service for device discovery"""

    def __init__(self, device_service, polling_interval: int = 60, subnet: str = "192.168.1.0/24"):
        self.device_service = device_service
        self.polling_interval = polling_interval
        self.subnet = subnet
        self.is_running = False
        self.last_scan_time = None
        self.scan_count = 0
        self.last_error = None
        self.task = None

    def set_interval(self, interval_seconds: int):
        """Set polling interval"""
        if interval_seconds <= 0:
            raise ValueError("Polling interval must be greater than 0")
        self.polling_interval = interval_seconds
        logger.info(f"Polling interval updated to {interval_seconds} seconds")

    def get_interval(self) -> int:
        """Get current polling interval"""
        return self.polling_interval

    async def start(self):
        """Start background polling"""
        if self.is_running:
            logger.warning("Polling already running")
            return

        self.is_running = True
        logger.info(f"Starting background polling (interval: {self.polling_interval}s, subnet: {self.subnet})")

        self.task = asyncio.create_task(self._polling_loop())

    async def stop(self):
        """Stop background polling"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Background polling stopped")

    async def _polling_loop(self):
        """Main polling loop"""
        while self.is_running:
            try:
                await self._perform_scan()
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                logger.debug("Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                self.last_error = str(e)
                # Wait before retrying on error
                await asyncio.sleep(min(self.polling_interval, 5))

    async def _perform_scan(self):
        """Perform a single scan"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.device_service.scan_and_update,
                self.subnet
            )

            self.last_scan_time = datetime.utcnow()
            self.scan_count += 1
            self.last_error = None

            logger.info(
                f"Scan #{self.scan_count}: Found {result['devices_found']} devices, "
                f"Added {result['devices_added']}, Updated {result['devices_updated']}, "
                f"Offline {result['devices_offline']}"
            )

        except Exception as e:
            logger.error(f"Error performing scan: {e}")
            self.last_error = str(e)

    def get_status(self) -> dict:
        """Get polling status"""
        return {
            'is_running': self.is_running,
            'polling_interval': self.polling_interval,
            'subnet': self.subnet,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'scan_count': self.scan_count,
            'last_error': self.last_error
        }


class PollingServiceManager:
    """Manages the background polling service"""

    _instance = None
    _poller = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PollingServiceManager, cls).__new__(cls)
        return cls._instance

    def initialize(self, device_service, polling_interval: int = 60, subnet: str = None):
        """Initialize the polling service"""
        if subnet is None:
            # Get subnet from environment or default
            subnet = os.getenv("NETWORK_SUBNET", "192.168.1.0/24")

        self._poller = BackgroundPoller(device_service, polling_interval, subnet)
        logger.info("Polling service manager initialized")

    async def start(self):
        """Start polling service"""
        if self._poller is None:
            raise RuntimeError("Polling service not initialized")
        await self._poller.start()

    async def stop(self):
        """Stop polling service"""
        if self._poller:
            await self._poller.stop()

    def get_poller(self) -> Optional[BackgroundPoller]:
        """Get the background poller instance"""
        return self._poller

    def set_interval(self, interval_seconds: int):
        """Set polling interval"""
        if self._poller is None:
            raise RuntimeError("Polling service not initialized")
        self._poller.set_interval(interval_seconds)

    def get_status(self) -> dict:
        """Get polling status"""
        if self._poller is None:
            return {'error': 'Polling service not initialized'}
        return self._poller.get_status()
