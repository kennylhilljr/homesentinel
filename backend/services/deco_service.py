"""
Deco Service for HomeSentinel
Manages Deco node data retrieval, enrichment, and caching
"""

import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from services.deco_client import DecoClient, InvalidCredentialsError, APIConnectionError

logger = logging.getLogger(__name__)


class DecoService:
    """
    Service for managing Deco node data with caching and enrichment
    """

    # Cache TTL in seconds (60 seconds)
    CACHE_TTL = 60

    def __init__(self, deco_client: Optional[DecoClient] = None):
        """
        Initialize Deco service

        Args:
            deco_client: DecoClient instance (creates new one if not provided)
        """
        self.deco_client = deco_client or DecoClient()
        self._nodes_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._wifi_config_cache: Optional[Dict[str, Any]] = None
        self._wifi_config_timestamp: Optional[datetime] = None
        self._qos_cache: Optional[Dict[str, Any]] = None
        self._qos_timestamp: Optional[datetime] = None

    def get_nodes_with_details(self) -> List[Dict[str, Any]]:
        """
        Get list of Deco nodes with enriched details

        Returns:
            List of node information dictionaries with enriched details:
            - node_id: Unique node identifier
            - node_name: Human-readable node name
            - firmware_version: Current firmware version
            - uptime_seconds: Node uptime in seconds
            - connected_clients: Number of connected clients on this node
            - signal_strength: Signal strength indicator (0-100%)
            - model: Node model name
            - status: Node operational status
            - last_updated: Timestamp of last data update

        Raises:
            InvalidCredentialsError: If not authenticated with Deco API
            APIConnectionError: If API request fails
        """
        # Check if cache is still valid
        if self._is_cache_valid():
            logger.debug("Returning cached node list")
            return self._nodes_cache

        try:
            logger.info("Fetching fresh node list from Deco API")
            raw_nodes = self.deco_client.get_node_list()

            # Enrich nodes with additional data
            enriched_nodes = []
            for node in raw_nodes:
                enriched_node = self._enrich_node_data(node)
                enriched_nodes.append(enriched_node)

            # Update cache
            self._nodes_cache = enriched_nodes
            self._cache_timestamp = datetime.now()

            logger.info(f"Retrieved and cached {len(enriched_nodes)} nodes")
            return enriched_nodes

        except InvalidCredentialsError as e:
            logger.error(f"Authentication failed: {e}")
            raise
        except APIConnectionError as e:
            logger.error(f"API connection error: {e}")
            raise

    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific node

        Args:
            node_id: Unique node identifier

        Returns:
            Node information dictionary or None if not found

        Raises:
            InvalidCredentialsError: If not authenticated with Deco API
            APIConnectionError: If API request fails
        """
        nodes = self.get_nodes_with_details()
        for node in nodes:
            if node.get("node_id") == node_id:
                return node
        return None

    def _is_cache_valid(self) -> bool:
        """
        Check if current cache is still valid

        Returns:
            True if cache exists and is within TTL, False otherwise
        """
        if not self._nodes_cache or not self._cache_timestamp:
            return False

        age = (datetime.now() - self._cache_timestamp).total_seconds()
        is_valid = age < self.CACHE_TTL

        if is_valid:
            logger.debug(f"Cache is valid ({age:.1f}s old, TTL: {self.CACHE_TTL}s)")
        else:
            logger.debug(f"Cache expired ({age:.1f}s old, TTL: {self.CACHE_TTL}s)")

        return is_valid

    def _enrich_node_data(self, raw_node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich raw node data with formatted and calculated fields

        Args:
            raw_node: Raw node data from Deco API

        Returns:
            Enriched node data dictionary
        """
        # Extract base node information
        node_id = raw_node.get("nodeID") or raw_node.get("node_id") or "unknown"
        node_name = raw_node.get("nodeName") or raw_node.get("node_name") or f"Node {node_id}"

        # Extract firmware version
        firmware = raw_node.get("fwVersion") or raw_node.get("firmware_version") or "unknown"

        # Extract uptime (may be in seconds or milliseconds)
        uptime_raw = raw_node.get("uptime") or raw_node.get("uptimeSeconds") or 0
        # If uptime is in milliseconds (> 100 years in seconds), convert to seconds
        if uptime_raw > 3153600000:  # ~100 years in seconds
            uptime_seconds = int(uptime_raw / 1000)
        else:
            uptime_seconds = int(uptime_raw)

        # Extract connected clients
        connected_clients = raw_node.get("connectedClients") or raw_node.get("connected_clients") or 0

        # Calculate signal strength (0-100%)
        # Deco API may provide signal as RSSI (negative dBm) or as a percentage
        signal_rssi = raw_node.get("signalRSSI") or raw_node.get("signal_rssi") or -70
        signal_strength = self._calculate_signal_strength(signal_rssi)

        # Extract model information
        model = raw_node.get("modelName") or raw_node.get("model_name") or "unknown"

        # Extract status
        status = raw_node.get("status") or raw_node.get("nodeStatus") or "unknown"

        # Create enriched node object
        enriched_node = {
            "node_id": str(node_id),
            "node_name": str(node_name),
            "firmware_version": str(firmware),
            "uptime_seconds": uptime_seconds,
            "connected_clients": int(connected_clients),
            "signal_strength": int(signal_strength),
            "model": str(model),
            "status": str(status),
            "last_updated": datetime.now().isoformat(),
            "raw_data": raw_node,  # Include raw data for debugging
        }

        return enriched_node

    def _calculate_signal_strength(self, signal_value: Any) -> int:
        """
        Calculate signal strength percentage from RSSI or raw value

        Args:
            signal_value: Signal value (RSSI in dBm or percentage)

        Returns:
            Signal strength as percentage (0-100)
        """
        try:
            signal_int = int(signal_value)

            # If value is negative (RSSI in dBm), convert to percentage
            if signal_int < 0:
                # RSSI conversion: -100dBm = 0%, -30dBm = 100%
                # Formula: percentage = 2 * (signal + 100)
                percentage = max(0, min(100, 2 * (signal_int + 100)))
                return percentage
            # If value is already a percentage (0-100), use as-is
            elif signal_int <= 100:
                return signal_int
            # If value is in unexpected range, normalize to 0-100
            else:
                # Assume 0-255 scale, convert to percentage
                return max(0, min(100, int((signal_int / 255) * 100)))

        except (ValueError, TypeError):
            logger.warning(f"Could not parse signal value: {signal_value}")
            return 0

    def clear_cache(self) -> None:
        """Clear the node cache"""
        self._nodes_cache = None
        self._cache_timestamp = None
        self._wifi_config_cache = None
        self._wifi_config_timestamp = None
        self._qos_cache = None
        self._qos_timestamp = None
        logger.info("All caches cleared")

    def get_wifi_config(self) -> Dict[str, Any]:
        """
        Get WiFi configuration from Deco API

        Returns:
            WiFi configuration dictionary containing:
            - ssid: Network name(s)
            - bands: Supported bands (2.4 GHz, 5 GHz, 6 GHz)
            - channel_2_4ghz: Current 2.4 GHz channel
            - channel_5ghz: Current 5 GHz channel
            - channel_6ghz: Current 6 GHz channel (if available)
            - band_steering: Whether band steering is enabled
            - last_updated: Timestamp of last update

        Raises:
            InvalidCredentialsError: If not authenticated with Deco API
            APIConnectionError: If API request fails
        """
        # Check if cache is still valid
        if self._is_cache_valid_wifi_config():
            logger.debug("Returning cached WiFi config")
            return self._wifi_config_cache

        try:
            logger.info("Fetching fresh WiFi config from Deco API")
            raw_config = self.deco_client.get_wifi_settings()

            # Enrich WiFi config with formatted fields
            enriched_config = self._enrich_wifi_config(raw_config)

            # Update cache
            self._wifi_config_cache = enriched_config
            self._wifi_config_timestamp = datetime.now()

            logger.info("Retrieved and cached WiFi config")
            return enriched_config

        except InvalidCredentialsError as e:
            logger.error(f"Authentication failed: {e}")
            raise
        except APIConnectionError as e:
            logger.error(f"API connection error: {e}")
            raise

    def get_qos_settings(self) -> Dict[str, Any]:
        """
        Get QoS (Quality of Service) settings and per-device bandwidth allocation

        Returns:
            QoS settings dictionary containing:
            - qos_enabled: Whether QoS is enabled
            - devices: List of devices with QoS settings:
                - device_id/name: Device identifier
                - mac_address: MAC address
                - priority: Priority level (High/Normal/Low)
                - bandwidth_limit: Bandwidth limit in Mbps (or null if no limit)
                - connection_type: WiFi/Wired
            - total_bandwidth: Total available bandwidth in Mbps
            - last_updated: Timestamp of last update

        Raises:
            InvalidCredentialsError: If not authenticated with Deco API
            APIConnectionError: If API request fails
        """
        # Check if cache is still valid
        if self._is_cache_valid_qos():
            logger.debug("Returning cached QoS settings")
            return self._qos_cache

        try:
            logger.info("Fetching fresh QoS settings from Deco API")

            # Get connected clients to correlate with QoS settings
            clients = self.deco_client.get_client_list()

            # Build QoS data from clients (since Deco API may not have dedicated QoS endpoint)
            qos_data = self._build_qos_from_clients(clients)

            # Update cache
            self._qos_cache = qos_data
            self._qos_timestamp = datetime.now()

            logger.info("Retrieved and cached QoS settings")
            return qos_data

        except InvalidCredentialsError as e:
            logger.error(f"Authentication failed: {e}")
            raise
        except APIConnectionError as e:
            logger.error(f"API connection error: {e}")
            raise

    def _is_cache_valid_wifi_config(self) -> bool:
        """
        Check if WiFi config cache is still valid

        Returns:
            True if cache exists and is within TTL, False otherwise
        """
        if not self._wifi_config_cache or not self._wifi_config_timestamp:
            return False

        age = (datetime.now() - self._wifi_config_timestamp).total_seconds()
        is_valid = age < self.CACHE_TTL

        if is_valid:
            logger.debug(f"WiFi config cache is valid ({age:.1f}s old, TTL: {self.CACHE_TTL}s)")
        else:
            logger.debug(f"WiFi config cache expired ({age:.1f}s old, TTL: {self.CACHE_TTL}s)")

        return is_valid

    def _is_cache_valid_qos(self) -> bool:
        """
        Check if QoS cache is still valid

        Returns:
            True if cache exists and is within TTL, False otherwise
        """
        if not self._qos_cache or not self._qos_timestamp:
            return False

        age = (datetime.now() - self._qos_timestamp).total_seconds()
        is_valid = age < self.CACHE_TTL

        if is_valid:
            logger.debug(f"QoS cache is valid ({age:.1f}s old, TTL: {self.CACHE_TTL}s)")
        else:
            logger.debug(f"QoS cache expired ({age:.1f}s old, TTL: {self.CACHE_TTL}s)")

        return is_valid

    def _enrich_wifi_config(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich raw WiFi config data with formatted fields

        Args:
            raw_config: Raw WiFi config from Deco API

        Returns:
            Enriched WiFi config dictionary
        """
        # Extract SSID(s)
        ssid = raw_config.get("ssid") or raw_config.get("SSID") or "Unknown"

        # Extract bands
        bands = []
        if raw_config.get("band_2_4ghz_enabled") or raw_config.get("is_2_4ghz") or "2.4" in str(raw_config.get("bands", "")):
            bands.append("2.4 GHz")
        if raw_config.get("band_5ghz_enabled") or raw_config.get("is_5ghz") or "5" in str(raw_config.get("bands", "")):
            bands.append("5 GHz")
        if raw_config.get("band_6ghz_enabled") or raw_config.get("is_6ghz") or "6" in str(raw_config.get("bands", "")):
            bands.append("6 GHz")

        # Default to common bands if not specified
        if not bands:
            bands = ["2.4 GHz", "5 GHz"]

        # Extract channel information
        channel_2_4ghz = raw_config.get("channel_2_4ghz") or raw_config.get("channel") or "Auto"
        channel_5ghz = raw_config.get("channel_5ghz") or raw_config.get("channel_5g") or "Auto"
        channel_6ghz = raw_config.get("channel_6ghz") or None

        # Extract band steering
        band_steering = raw_config.get("band_steering_enabled") or raw_config.get("band_steering") or False

        enriched_config = {
            "ssid": str(ssid),
            "bands": bands,
            "channel_2_4ghz": str(channel_2_4ghz),
            "channel_5ghz": str(channel_5ghz),
            "channel_6ghz": str(channel_6ghz) if channel_6ghz else None,
            "band_steering_enabled": bool(band_steering),
            "last_updated": datetime.now().isoformat(),
            "raw_data": raw_config,
        }

        return enriched_config

    def _build_qos_from_clients(self, clients: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build QoS data from connected clients

        Args:
            clients: List of connected clients from Deco API

        Returns:
            QoS settings dictionary with per-device bandwidth info
        """
        devices = []

        for client in clients:
            device_entry = {
                "device_name": client.get("name") or client.get("clientName") or "Unknown",
                "mac_address": client.get("macAddress") or client.get("mac_address") or "Unknown",
                "priority": client.get("priority") or "Normal",
                "bandwidth_limit_mbps": client.get("bandwidth_limit") or client.get("bandwidth") or None,
                "connection_type": client.get("connectionType") or client.get("type") or "WiFi",
                "ip_address": client.get("ipAddress") or client.get("ip_address") or "Unknown",
            }
            devices.append(device_entry)

        qos_data = {
            "qos_enabled": True,
            "devices": devices,
            "total_devices": len(devices),
            "total_bandwidth_mbps": None,  # Not typically available from Deco API
            "last_updated": datetime.now().isoformat(),
            "raw_data": {"clients": clients},
        }

        return qos_data

    def update_wifi_config(
        self,
        ssid: Optional[str] = None,
        password: Optional[str] = None,
        band_steering: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update WiFi configuration settings

        Args:
            ssid: New SSID (1-32 characters)
            password: New WiFi password (8+ characters)
            band_steering: Enable/disable band steering

        Returns:
            Dictionary containing:
            - success: Whether update was successful
            - message: Status message
            - updated_config: Updated WiFi configuration from API
            - verification_status: Status of verification ("pending", "verified", "timeout", "error")
            - timestamp: Timestamp of update

        Raises:
            ValueError: If input validation fails
            InvalidCredentialsError: If not authenticated with Deco API
            APIConnectionError: If API request fails
        """
        # Validate inputs
        if ssid is not None:
            ssid = str(ssid).strip()
            if len(ssid) < 1 or len(ssid) > 32:
                raise ValueError("SSID must be between 1 and 32 characters")

        if password is not None:
            password = str(password)
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters")

        try:
            logger.info(f"Updating WiFi config: SSID={ssid is not None}, Password={password is not None}, BandSteering={band_steering}")

            # Call Deco API to update settings
            api_response = self.deco_client.update_wifi_settings(
                ssid=ssid,
                password=password,
                band_steering=band_steering,
            )

            logger.info(f"WiFi config update response: {api_response}")

            # Clear WiFi config cache to force refresh on next read
            self._wifi_config_cache = None
            self._wifi_config_timestamp = None
            logger.info("Cleared WiFi config cache after update")

            # Fetch fresh config from API to verify changes
            fresh_config = self.get_wifi_config()

            return {
                "success": True,
                "message": "WiFi configuration updated successfully",
                "updated_config": fresh_config,
                "verification_status": "pending",  # Frontend handles verification polling
                "timestamp": datetime.now().isoformat(),
            }

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise
        except InvalidCredentialsError as e:
            logger.error(f"Authentication failed during WiFi config update: {e}")
            raise
        except APIConnectionError as e:
            logger.error(f"API connection error during WiFi config update: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating WiFi config: {e}")
            raise APIConnectionError(f"Failed to update WiFi configuration: {str(e)}")
