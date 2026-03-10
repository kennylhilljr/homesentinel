"""
Alarm.com API client for HomeSentinel.
# 2026-03-10: Wraps pyalarmdotcomajax for async Alarm.com integration.
# Handles login, 2FA cookie persistence, device state, and partition commands.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class AlarmComAuthError(Exception):
    """Raised when Alarm.com authentication fails."""


class AlarmComAPIError(Exception):
    """Raised when Alarm.com API requests fail."""


class AlarmComClient:
    """Client for Alarm.com security system integration."""

    def __init__(
        self,
        username: str = "",
        password: str = "",
        two_factor_cookie: str = "",
    ):
        env_user = os.getenv("ALARM_COM_USERNAME", "")
        env_pass = os.getenv("ALARM_COM_PASSWORD", "")
        env_2fa = os.getenv("ALARM_COM_2FA_COOKIE", "")

        self.username = username or env_user
        self.password = password or env_pass
        self.two_factor_cookie = two_factor_cookie or env_2fa

        self._controller = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._logged_in = False

    def set_credentials(self, username: str, password: str, two_factor_cookie: str = ""):
        """Update credentials and reset session."""
        self.username = username
        self.password = password
        if two_factor_cookie:
            self.two_factor_cookie = two_factor_cookie
        self._controller = None
        self._logged_in = False

    async def _ensure_session(self):
        """Create aiohttp session if needed."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def login(self) -> Dict[str, Any]:
        """Authenticate with Alarm.com. Returns status info.
        Raises AlarmComAuthError on failure, or returns OTP info if 2FA needed.
        """
        if not self.username or not self.password:
            raise AlarmComAuthError("Alarm.com credentials not configured")

        try:
            from pyalarmdotcomajax import AlarmController
            from pyalarmdotcomajax.exceptions import (
                AuthenticationFailed,
                OtpRequired,
            )
        except ImportError:
            raise AlarmComAPIError(
                "pyalarmdotcomajax not installed. Run: pip install pyalarmdotcomajax"
            )

        await self._ensure_session()
        self._controller = AlarmController(
            username=self.username,
            password=self.password,
            websession=self._session,
            twofactorcookie=self.two_factor_cookie or None,
        )

        try:
            await self._controller.async_login()
            self._logged_in = True
            return {"success": True, "message": "Logged in to Alarm.com"}
        except OtpRequired as e:
            # 2FA required — caller must handle OTP flow
            return {
                "success": False,
                "otp_required": True,
                "otp_types": [str(t) for t in getattr(e, "otp_types", ["app"])],
                "message": "Two-factor authentication required",
            }
        except AuthenticationFailed as e:
            self._logged_in = False
            raise AlarmComAuthError(f"Login failed: {e}")
        except Exception as e:
            self._logged_in = False
            raise AlarmComAPIError(f"Login error: {e}")

    async def request_otp(self, method: str = "app") -> Dict[str, Any]:
        """Request OTP code via specified method (app, email, sms)."""
        if not self._controller:
            raise AlarmComAPIError("Must call login() first")
        try:
            from pyalarmdotcomajax.const import OtpType
            otp_map = {"app": OtpType.APP, "email": OtpType.EMAIL, "sms": OtpType.SMS}
            otp_type = otp_map.get(method, OtpType.APP)
            await self._controller.async_request_otp(otp_type)
            return {"success": True, "method": method}
        except Exception as e:
            raise AlarmComAPIError(f"Failed to request OTP: {e}")

    async def submit_otp(self, code: str, method: str = "app") -> Dict[str, Any]:
        """Submit OTP code to complete 2FA login.
        # 2026-03-10: async_submit_otp requires (code, method, device_name, remember_me).
        """
        if not self._controller:
            raise AlarmComAPIError("Must call login() first")
        try:
            from pyalarmdotcomajax.const import OtpType
            otp_map = {"app": OtpType.APP, "email": OtpType.EMAIL, "sms": OtpType.SMS}
            otp_type = otp_map.get(method, OtpType.APP)

            await self._controller.async_submit_otp(
                code=code,
                method=otp_type,
                device_name="HomeSentinel",
                remember_me=True,
            )
            # Save the 2FA cookie for future logins
            cookie = self._controller.two_factor_cookie
            if cookie:
                self.two_factor_cookie = cookie
            self._logged_in = True
            return {
                "success": True,
                "two_factor_cookie": self.two_factor_cookie,
                "message": "2FA verified, logged in",
            }
        except Exception as e:
            raise AlarmComAPIError(f"OTP submission failed: {e}")

    async def _ensure_logged_in(self):
        """Ensure we're logged in, attempt login if not."""
        if not self._logged_in or not self._controller:
            result = await self.login()
            if result.get("otp_required"):
                raise AlarmComAuthError("2FA required — complete OTP flow first")

    async def update_devices(self):
        """Fetch latest device states from Alarm.com."""
        await self._ensure_logged_in()
        try:
            await self._controller.async_update()
        except Exception as e:
            self._logged_in = False
            raise AlarmComAPIError(f"Failed to update devices: {e}")

    def _serialize_device(self, device) -> Dict[str, Any]:
        """Convert a pyalarmdotcomajax device to a serializable dict."""
        state_val = None
        if hasattr(device, "state") and device.state is not None:
            state_val = device.state.name if hasattr(device.state, "name") else str(device.state)

        battery = None
        if hasattr(device, "battery_state") and device.battery_state is not None:
            battery = str(device.battery_state)

        return {
            "id": str(device.id_) if hasattr(device, "id_") else str(getattr(device, "id", "")),
            "name": getattr(device, "name", "Unknown"),
            "state": state_val,
            "mac_address": getattr(device, "mac_address", None),
            "battery": battery,
            "malfunction": getattr(device, "malfunction", False),
            "device_type": type(device).__name__,
        }

    async def get_partitions(self) -> List[Dict[str, Any]]:
        """Get alarm partitions with current arm/disarm state."""
        await self._ensure_logged_in()
        await self.update_devices()
        partitions = []
        for p in self._controller.devices.partitions.values():
            data = self._serialize_device(p)
            data["uncleared_issues"] = getattr(p, "uncleared_issues", False)
            partitions.append(data)
        return partitions

    async def get_sensors(self) -> List[Dict[str, Any]]:
        """Get all sensors (door, window, motion, etc.)."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(s) for s in self._controller.devices.sensors.values()]

    async def get_locks(self) -> List[Dict[str, Any]]:
        """Get smart lock states."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(l) for l in self._controller.devices.locks.values()]

    async def get_lights(self) -> List[Dict[str, Any]]:
        """Get Alarm.com-connected light states."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(l) for l in self._controller.devices.lights.values()]

    async def get_thermostats(self) -> List[Dict[str, Any]]:
        """Get thermostat states."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(t) for t in self._controller.devices.thermostats.values()]

    async def get_cameras(self) -> List[Dict[str, Any]]:
        """Get camera devices."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(c) for c in self._controller.devices.cameras.values()]

    async def get_garage_doors(self) -> List[Dict[str, Any]]:
        """Get garage door states."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(g) for g in self._controller.devices.garage_doors.values()]

    async def get_water_sensors(self) -> List[Dict[str, Any]]:
        """Get water/flood sensor states."""
        await self._ensure_logged_in()
        await self.update_devices()
        return [self._serialize_device(w) for w in self._controller.devices.water_sensors.values()]

    async def get_all_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all device categories in one call."""
        await self._ensure_logged_in()
        await self.update_devices()
        registry = self._controller.devices
        return {
            "partitions": [self._serialize_device(d) for d in registry.partitions.values()],
            "sensors": [self._serialize_device(d) for d in registry.sensors.values()],
            "locks": [self._serialize_device(d) for d in registry.locks.values()],
            "lights": [self._serialize_device(d) for d in registry.lights.values()],
            "thermostats": [self._serialize_device(d) for d in registry.thermostats.values()],
            "cameras": [self._serialize_device(d) for d in registry.cameras.values()],
            "garage_doors": [self._serialize_device(d) for d in registry.garage_doors.values()],
            "water_sensors": [self._serialize_device(d) for d in registry.water_sensors.values()],
        }

    async def arm_away(self, partition_id: str) -> Dict[str, Any]:
        """Arm partition in Away mode."""
        return await self._send_partition_command(partition_id, "arm_away")

    async def arm_stay(self, partition_id: str) -> Dict[str, Any]:
        """Arm partition in Stay mode."""
        return await self._send_partition_command(partition_id, "arm_stay")

    async def disarm(self, partition_id: str) -> Dict[str, Any]:
        """Disarm partition."""
        return await self._send_partition_command(partition_id, "disarm")

    async def _send_partition_command(self, partition_id: str, command: str) -> Dict[str, Any]:
        """Send arm/disarm command to a partition.
        # 2026-03-10: async_send_command signature is (device_type, event, device_id).
        """
        await self._ensure_logged_in()

        partition = self._controller.devices.partitions.get(partition_id)
        if not partition:
            raise AlarmComAPIError(f"Partition {partition_id} not found")

        try:
            from pyalarmdotcomajax.devices import DeviceType
            from pyalarmdotcomajax.devices.partition import Partition
            cmd_map = {
                "arm_away": Partition.Command.ARM_AWAY,
                "arm_stay": Partition.Command.ARM_STAY,
                "disarm": Partition.Command.DISARM,
            }
            cmd = cmd_map.get(command)
            if not cmd:
                raise AlarmComAPIError(f"Unknown partition command: {command}")

            await self._controller.async_send_command(
                device_type=DeviceType.PARTITION,
                event=cmd,
                device_id=partition_id,
            )
            return {"success": True, "command": command, "partition_id": partition_id}
        except AlarmComAPIError:
            raise
        except Exception as e:
            raise AlarmComAPIError(f"Partition command failed: {e}")

    async def lock(self, lock_id: str) -> Dict[str, Any]:
        """Lock a smart lock."""
        return await self._send_lock_command(lock_id, "lock")

    async def unlock(self, lock_id: str) -> Dict[str, Any]:
        """Unlock a smart lock."""
        return await self._send_lock_command(lock_id, "unlock")

    async def _send_lock_command(self, lock_id: str, command: str) -> Dict[str, Any]:
        """Send lock/unlock command.
        # 2026-03-10: async_send_command signature is (device_type, event, device_id).
        """
        await self._ensure_logged_in()

        lock_dev = self._controller.devices.locks.get(lock_id)
        if not lock_dev:
            raise AlarmComAPIError(f"Lock {lock_id} not found")

        try:
            from pyalarmdotcomajax.devices import DeviceType
            from pyalarmdotcomajax.devices.lock import Lock
            cmd_map = {
                "lock": Lock.Command.LOCK,
                "unlock": Lock.Command.UNLOCK,
            }
            cmd = cmd_map.get(command)
            if not cmd:
                raise AlarmComAPIError(f"Unknown lock command: {command}")

            await self._controller.async_send_command(
                device_type=DeviceType.LOCK,
                event=cmd,
                device_id=lock_id,
            )
            return {"success": True, "command": command, "lock_id": lock_id}
        except AlarmComAPIError:
            raise
        except Exception as e:
            raise AlarmComAPIError(f"Lock command failed: {e}")

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._controller = None
        self._logged_in = False

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
