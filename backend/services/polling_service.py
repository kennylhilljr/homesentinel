"""
Background Polling Service for HomeSentinel
Implements periodic ARP scanning and device updates with home network detection
"""

import asyncio
import logging
import subprocess
import socket
from datetime import datetime
from typing import Optional
import os

logger = logging.getLogger(__name__)

# 2026-03-12: Home network detection — Option A (gateway) with Option B (SSID) fallback
HOME_GATEWAY = os.getenv("HOME_GATEWAY_IP", "192.168.12.1")
HOME_SSIDS = {"USVA42_Home", "USVA42_MLO"}


def check_home_network() -> dict:
    """Detect whether we're on the home network.
    Option A: Try to reach the home gateway (Chester at 192.168.12.1).
    Option B fallback: Check current SSID against known home SSIDs.
    Returns dict with is_home, method, and detail.
    """
    # Option A: Gateway ping (fast — 1 second timeout)
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", HOME_GATEWAY],
            capture_output=True, timeout=3
        )
        if result.returncode == 0:
            return {"is_home": True, "method": "gateway", "detail": f"{HOME_GATEWAY} reachable"}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Option B fallback: SSID check (macOS)
    try:
        result = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    ssid = line.split(":", 1)[1].strip()
                    if ssid in HOME_SSIDS:
                        return {"is_home": True, "method": "ssid", "detail": ssid}
                    return {"is_home": False, "method": "ssid", "detail": ssid}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Neither method worked — assume away
    return {"is_home": False, "method": "none", "detail": "gateway unreachable, SSID unknown"}


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
        # 2026-03-12: Home/away state
        self.is_home = False
        self.home_detail = ""
        self.home_method = ""
        self.auto_scan_paused = False  # User-controlled pause toggle

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
        """Main polling loop — skips scan when away from home network"""
        while self.is_running:
            try:
                # 2026-03-12: Check home network before scanning
                loop = asyncio.get_event_loop()
                status = await loop.run_in_executor(None, check_home_network)
                self.is_home = status["is_home"]
                self.home_method = status["method"]
                self.home_detail = status["detail"]

                if self.auto_scan_paused:
                    logger.debug("Auto-scan paused by user — skipping")
                elif self.is_home:
                    await self._perform_scan()
                else:
                    logger.debug(f"Away from home ({self.home_detail}) — skipping auto-scan")

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

            # 2026-03-12: Push scan results to SSE subscribers
            try:
                from routes.sse import publish_event
                publish_event("device_update", {
                    "device_count": result.get("devices_found", 0),
                    "online": result.get("devices_found", 0) - result.get("devices_offline", 0),
                    "offline": result.get("devices_offline", 0),
                    "added": result.get("devices_added", 0),
                    "updated": result.get("devices_updated", 0),
                    "scan_number": self.scan_count,
                })
            except Exception as sse_err:
                logger.debug(f"SSE publish failed (non-fatal): {sse_err}")

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
            'last_error': self.last_error,
            'is_home': self.is_home,
            'home_method': self.home_method,
            'home_detail': self.home_detail,
            'auto_scan_paused': self.auto_scan_paused,
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
