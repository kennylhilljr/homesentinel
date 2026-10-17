"""
Alexa Service for HomeSentinel
Business logic layer for Alexa Smart Home device management
"""

import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlexaService:
    """
    Business logic for Alexa Smart Home integration
    Handles device inventory caching, state management, and command dispatch
    """

    CACHE_TTL = 300  # 5 minutes
    STALENESS_THRESHOLD = 300  # 5 minutes — state older than this is "stale"

    def __init__(self, alexa_client, db=None):
        self.alexa_client = alexa_client
        self.db = db
        self._devices_cache: Optional[List[Dict]] = None
        self._cache_time: Optional[datetime] = None

    def _is_cache_valid(self) -> bool:
        if self._devices_cache is None or self._cache_time is None:
            return False
        return (datetime.now() - self._cache_time).total_seconds() < self.CACHE_TTL

    def clear_cache(self):
        self._devices_cache = None
        self._cache_time = None

    def get_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get all Alexa devices with normalized structure.
        Tries web API first (returns ALL user's devices), falls back to skill discovery.
        """
        if not force_refresh and self._is_cache_valid():
            return self._devices_cache

        devices = []

        # Try web API first — returns devices from all linked skills
        try:
            raw_appliances = self.alexa_client.get_smart_home_devices()
            if raw_appliances:
                logger.info(f"Web API returned {len(raw_appliances)} appliances")
                devices = self._normalize_web_appliances(raw_appliances)
        except Exception as e:
            logger.warning(f"Web API device fetch failed: {e}")

        # Fallback to skill discovery directive
        if not devices:
            try:
                raw_endpoints = self.alexa_client.discover_devices()
                for ep in raw_endpoints:
                    capabilities = ep.get("capabilities", [])
                    cap_interfaces = [c.get("interface", "") for c in capabilities]
                    device_type = self._classify_device(cap_interfaces, ep)
                    is_echo = device_type == "echo"
                    device = {
                        "endpoint_id": ep.get("endpointId", ""),
                        "friendly_name": ep.get("friendlyName", "Unknown"),
                        "description": ep.get("description", ""),
                        "manufacturer": ep.get("manufacturerName", ""),
                        "model": ep.get("modelName", ep.get("model", "")),
                        "device_type": device_type,
                        "capabilities": cap_interfaces,
                        "is_echo_device": is_echo,
                        "display_categories": ep.get("displayCategories", []),
                        "last_state": None,
                        "state_updated_at": None,
                        "is_stale": True,
                        "raw_data": ep,
                    }
                    devices.append(device)
            except Exception as e:
                logger.warning(f"Skill discovery also failed: {e}")

        # Persist and cache
        for device in devices:
            if self.db:
                self._save_device_to_db(device)

        self._devices_cache = devices
        self._cache_time = datetime.now()
        logger.info(f"Cached {len(devices)} Alexa devices")
        return devices

    def _normalize_web_appliances(self, appliances: List[Dict]) -> List[Dict[str, Any]]:
        """Normalize behaviors/entities API data to our standard device format."""
        devices = []
        for entity in appliances:
            entity_id = entity.get("id", "")
            friendly_name = entity.get("displayName", "Unknown")
            description = entity.get("description", "")
            availability = entity.get("availability", "UNAVAILABLE")
            is_reachable = availability == "AVAILABLE"

            provider = entity.get("providerData", {})
            device_type_raw = provider.get("deviceType", "OTHER")
            category = provider.get("categoryType", "APPLIANCE")

            # Skip groups — they aren't real devices
            if category == "GROUP":
                continue

            # Map device type
            device_type = self._classify_from_appliance_type(device_type_raw)
            is_echo = device_type == "echo" or device_type_raw == "ALEXA_VOICE_ENABLED"
            if device_type_raw == "ALEXA_VOICE_ENABLED":
                device_type = "echo"

            # Extract capabilities from supportedOperations
            operations = entity.get("supportedOperations", [])
            capabilities = []
            for op in operations:
                if isinstance(op, str):
                    capabilities.append(op)

            # Extract DMS identifiers (serial numbers)
            dms = provider.get("dmsDeviceIdentifiers", [])
            serial_number = ""
            if dms and isinstance(dms[0], dict):
                serial_number = dms[0].get("deviceSerialNumber", "")

            # Scene detection
            is_scene = category == "SCENE" or device_type_raw == "SCENE_TRIGGER"

            device = {
                "endpoint_id": entity_id,
                "friendly_name": friendly_name,
                "description": description,
                "manufacturer": "",
                "model": device_type_raw,
                "device_type": "scene" if is_scene else device_type,
                "capabilities": capabilities,
                "is_echo_device": is_echo,
                "display_categories": [device_type_raw],
                "last_state": None,
                "state_updated_at": None,
                "is_stale": not is_reachable,
                "parsed_state": {},
                "is_reachable": is_reachable,
                "serial_number": serial_number,
                "category": category,
                "raw_data": entity,
            }
            devices.append(device)
        return devices

    def _classify_from_appliance_type(self, app_type: str) -> str:
        """Map Alexa applianceType to our device type."""
        app_type = app_type.upper()
        mapping = {
            "LIGHT": "light",
            "SMARTPLUG": "plug",
            "SWITCH": "plug",
            "THERMOSTAT": "thermostat",
            "TEMPERATURE_SENSOR": "thermostat",
            "SMARTLOCK": "lock",
            "LOCK": "lock",
            "CAMERA": "camera",
            "DOORBELL": "camera",
            "SPEAKER": "echo",
            "ECHO": "echo",
            "HUB": "hub",
            "SCENE_TRIGGER": "scene",
            "ACTIVITY_TRIGGER": "scene",
            "FAN": "fan",
            "CONTACT_SENSOR": "sensor",
            "MOTION_SENSOR": "sensor",
            "TV": "tv",
            "WASHER": "washer",
            "DRYER": "dryer",
            "AIR_CONDITIONER": "climate",
            "SECURITY_PANEL": "security",
            "ALEXA_VOICE_ENABLED": "echo",
            "OTHER": "other",
        }
        return mapping.get(app_type, "other")

    def _classify_device(self, capabilities: List[str], endpoint: Dict) -> str:
        """Classify device type from capabilities and display categories"""
        categories = [c.upper() for c in endpoint.get("displayCategories", [])]

        if "SPEAKER" in categories or "ECHO" in categories:
            return "echo"
        if "LIGHT" in categories:
            return "light"
        if "SMARTPLUG" in categories or "SWITCH" in categories:
            return "plug"
        if "THERMOSTAT" in categories or "TEMPERATURE_SENSOR" in categories:
            return "thermostat"
        if "SMARTLOCK" in categories or "LOCK" in categories:
            return "lock"
        if "CAMERA" in categories:
            return "camera"

        # Fallback to capability-based classification
        if "Alexa.ColorController" in capabilities or "Alexa.BrightnessController" in capabilities:
            return "light"
        if "Alexa.ThermostatController" in capabilities:
            return "thermostat"
        if "Alexa.LockController" in capabilities:
            return "lock"
        if "Alexa.PowerController" in capabilities:
            return "plug"

        return "other"

    def get_device_with_state(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get a single device with its current state"""
        devices = self.get_devices()
        device = next((d for d in devices if d["endpoint_id"] == endpoint_id), None)
        if not device:
            return None

        # Fetch fresh state
        state = self.alexa_client.get_device_state(endpoint_id)
        now = datetime.now()

        device["last_state"] = state
        device["state_updated_at"] = now.isoformat()
        device["is_stale"] = False

        # Parse common state values for easier frontend consumption
        device["parsed_state"] = self._parse_state(state, device["capabilities"])

        if self.db:
            self._save_device_state_to_db(endpoint_id, state, now)

        return device

    def get_all_devices_with_state(self) -> List[Dict[str, Any]]:
        """Get all devices and fetch state for each"""
        devices = self.get_devices()
        for device in devices:
            try:
                state = self.alexa_client.get_device_state(device["endpoint_id"])
                now = datetime.now()
                device["last_state"] = state
                device["state_updated_at"] = now.isoformat()
                device["is_stale"] = False
                device["parsed_state"] = self._parse_state(state, device["capabilities"])
            except Exception as e:
                logger.warning(f"Failed to get state for {device['endpoint_id']}: {e}")
                device["parsed_state"] = {}
                device["is_stale"] = True
        return devices

    def _parse_state(self, state: Dict, capabilities: List[str]) -> Dict[str, Any]:
        """Parse raw state into simplified key-value pairs"""
        parsed = {}

        power = state.get("Alexa.PowerController.powerState", {})
        if power:
            parsed["power"] = power.get("value", "OFF")

        brightness = state.get("Alexa.BrightnessController.brightness", {})
        if brightness:
            parsed["brightness"] = brightness.get("value", 0)

        color = state.get("Alexa.ColorController.color", {})
        if color:
            parsed["color"] = color.get("value", {})

        color_temp = state.get("Alexa.ColorTemperatureController.colorTemperatureInKelvin", {})
        if color_temp:
            parsed["color_temperature"] = color_temp.get("value", 0)

        temp = state.get("Alexa.TemperatureSensor.temperature", {})
        if temp:
            parsed["temperature"] = temp.get("value", {})

        target = state.get("Alexa.ThermostatController.targetSetpoint", {})
        if target:
            parsed["target_temperature"] = target.get("value", {})

        mode = state.get("Alexa.ThermostatController.thermostatMode", {})
        if mode:
            parsed["thermostat_mode"] = mode.get("value", "OFF")

        lock = state.get("Alexa.LockController.lockState", {})
        if lock:
            parsed["lock_state"] = lock.get("value", "UNLOCKED")

        return parsed

    def send_command(self, endpoint_id: str, command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Dispatch a command to an Alexa device"""
        params = params or {}

        if command == "power_on":
            return self.alexa_client.send_power_command(endpoint_id, True)
        elif command == "power_off":
            return self.alexa_client.send_power_command(endpoint_id, False)
        elif command == "set_brightness":
            return self.alexa_client.set_brightness(endpoint_id, params.get("brightness", 100))
        elif command == "set_color":
            return self.alexa_client.set_color(
                endpoint_id,
                params.get("hue", 0),
                params.get("saturation", 1.0),
                params.get("brightness", 1.0),
            )
        elif command == "set_color_temperature":
            return self.alexa_client.set_color_temperature(endpoint_id, params.get("temperature", 2700))
        elif command == "set_thermostat":
            return self.alexa_client.set_thermostat(
                endpoint_id,
                params.get("temperature", 72),
                params.get("scale", "FAHRENHEIT"),
            )
        elif command == "set_thermostat_mode":
            return self.alexa_client.set_thermostat_mode(endpoint_id, params.get("mode", "AUTO"))
        elif command == "lock":
            return self.alexa_client.send_lock_command(endpoint_id, True)
        elif command == "unlock":
            return self.alexa_client.send_lock_command(endpoint_id, False)
        else:
            raise ValueError(f"Unknown command: {command}")

    def get_echo_devices(self) -> List[Dict[str, Any]]:
        """Get Echo/Alexa hardware devices."""
        # Try web API for real Echo hardware inventory
        try:
            raw = self.alexa_client.get_echo_devices_web()
            if raw:
                echo_devices = []
                for d in raw:
                    if not isinstance(d, dict):
                        continue
                    echo_devices.append({
                        "endpoint_id": d.get("serialNumber", d.get("deviceSerialNumber", "")),
                        "friendly_name": d.get("accountName", d.get("deviceAccountName", "Echo")),
                        "description": d.get("deviceType", ""),
                        "manufacturer": "Amazon",
                        "model": d.get("deviceFamily", d.get("deviceType", "")),
                        "device_type": "echo",
                        "capabilities": [],
                        "is_echo_device": True,
                        "online": d.get("online", True),
                    })
                if echo_devices:
                    return echo_devices
        except Exception as e:
            logger.warning(f"Web API Echo device fetch failed: {e}")

        # Fallback: filter from smart home discovery
        devices = self.get_devices()
        return [d for d in devices if d.get("is_echo_device")]

    def _save_device_to_db(self, device: Dict):
        """Persist Alexa device to database"""
        if not self.db:
            return
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO alexa_devices
                    (endpoint_id, friendly_name, description, manufacturer, model,
                     device_type, capabilities, is_echo_device, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    device["endpoint_id"],
                    device["friendly_name"],
                    device["description"],
                    device["manufacturer"],
                    device["model"],
                    device["device_type"],
                    json.dumps(device["capabilities"]),
                    1 if device["is_echo_device"] else 0,
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save Alexa device to DB: {e}")

    def _save_device_state_to_db(self, endpoint_id: str, state: Dict, timestamp: datetime):
        """Persist device state to database"""
        if not self.db:
            return
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE alexa_devices
                    SET last_state = ?, state_updated_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE endpoint_id = ?
                """, (json.dumps(state), timestamp, endpoint_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save Alexa device state: {e}")
