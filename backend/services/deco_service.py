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
        logger.info("Node cache cleared")
