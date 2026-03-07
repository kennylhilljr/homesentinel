"""
Correlation Service for HomeSentinel
Correlates Deco mesh network clients with locally-discovered devices by MAC address
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from services.deco_service import DecoService
from db import Database, NetworkDeviceRepository

logger = logging.getLogger(__name__)


class CorrelationService:
    """
    Service for correlating Deco connected clients with locally-discovered NetworkDevices
    Matches devices by MAC address to provide unified view of network
    """

    def __init__(self, deco_service: DecoService, device_repo: NetworkDeviceRepository):
        """
        Initialize correlation service

        Args:
            deco_service: DecoService instance for fetching Deco clients
            device_repo: NetworkDeviceRepository for accessing local device data
        """
        self.deco_service = deco_service
        self.device_repo = device_repo

    def normalize_mac_address(self, mac_address: str) -> str:
        """
        Normalize MAC address to lowercase with colons for comparison

        Args:
            mac_address: MAC address in any format (00:11:22:33:44:55, 00-11-22-33-44-55, etc)

        Returns:
            Normalized MAC address in lowercase with colons
        """
        if not mac_address:
            return ""
        # Remove all separators and convert to lowercase
        cleaned = mac_address.lower().replace("-", "").replace(":", "").replace(" ", "")
        # Reformat with colons
        if len(cleaned) == 12:
            return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
        return mac_address.lower()

    def get_deco_clients(self) -> List[Dict[str, Any]]:
        """
        Fetch list of Deco connected clients

        Returns:
            List of client dictionaries from Deco API

        Raises:
            Exception: If Deco API request fails
        """
        try:
            logger.info("Fetching Deco clients")
            clients = self.deco_service.deco_client.get_client_list()
            logger.info(f"Retrieved {len(clients)} Deco clients")
            return clients
        except Exception as e:
            logger.error(f"Failed to fetch Deco clients: {e}")
            raise

    def get_lan_devices(self) -> List[Dict[str, Any]]:
        """
        Fetch list of locally-discovered network devices

        Returns:
            List of device dictionaries from database
        """
        try:
            logger.info("Fetching LAN devices from database")
            devices = self.device_repo.list_all()
            logger.info(f"Retrieved {len(devices)} LAN devices")
            return devices
        except Exception as e:
            logger.error(f"Failed to fetch LAN devices: {e}")
            raise

    def correlate_by_mac(
        self, deco_clients: List[Dict[str, Any]], lan_devices: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Correlate Deco clients with LAN devices by MAC address

        Args:
            deco_clients: List of Deco connected clients
            lan_devices: List of locally-discovered network devices

        Returns:
            Tuple of (merged_devices, unmatched_deco_clients, unmatched_lan_devices)
        """
        merged_devices = []
        matched_deco_macs = set()
        matched_lan_macs = set()

        # Create MAC to device mapping for LAN devices
        lan_mac_map = {}
        for device in lan_devices:
            mac = device.get("mac_address", "")
            if mac:
                normalized_mac = self.normalize_mac_address(mac)
                lan_mac_map[normalized_mac] = device

        # Match Deco clients with LAN devices
        for deco_client in deco_clients:
            deco_mac = deco_client.get("macAddress") or deco_client.get("mac_address") or ""
            if not deco_mac:
                logger.debug(f"Deco client missing MAC address: {deco_client}")
                continue

            normalized_deco_mac = self.normalize_mac_address(deco_mac)

            # Look for matching LAN device
            if normalized_deco_mac in lan_mac_map:
                matched_deco_macs.add(normalized_deco_mac)
                lan_device = lan_mac_map[normalized_deco_mac]
                matched_lan_macs.add(normalized_deco_mac)

                # Merge data
                merged = self._merge_device_data(deco_client, lan_device)
                merged_devices.append(merged)
            else:
                # Deco client without LAN device match
                logger.debug(f"Deco client {deco_mac} has no matching LAN device")

        # Identify unmatched devices
        unmatched_deco_clients = []
        for deco_client in deco_clients:
            deco_mac = deco_client.get("macAddress") or deco_client.get("mac_address") or ""
            if deco_mac:  # Only include if MAC is present
                normalized_deco_mac = self.normalize_mac_address(deco_mac)
                if normalized_deco_mac not in matched_deco_macs:
                    unmatched_deco_clients.append(deco_client)

        unmatched_lan_devices = [
            device for device in lan_devices
            if self.normalize_mac_address(device.get("mac_address", ""))
            not in matched_lan_macs
        ]

        return merged_devices, unmatched_deco_clients, unmatched_lan_devices

    def _merge_device_data(self, deco_client: Dict[str, Any], lan_device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge Deco client data with LAN device data

        Args:
            deco_client: Deco client dictionary
            lan_device: LAN device dictionary from database

        Returns:
            Merged device dictionary with both Deco and LAN data
        """
        # Extract Deco client name (various possible field names)
        deco_client_name = (
            deco_client.get("clientName")
            or deco_client.get("client_name")
            or deco_client.get("name")
            or "Unknown"
        )

        # Extract MAC (normalized)
        mac = lan_device.get("mac_address", "")
        normalized_mac = self.normalize_mac_address(mac)

        # Extract LAN device data
        device_id = lan_device.get("device_id", "")
        current_ip = lan_device.get("current_ip", "")
        vendor_name = lan_device.get("vendor_name", "")
        friendly_name = lan_device.get("friendly_name", "")
        status = lan_device.get("status", "offline")
        first_seen = lan_device.get("first_seen", "")
        last_seen = lan_device.get("last_seen", "")

        # Build merged device record
        merged_device = {
            "device_id": device_id,
            "mac_address": normalized_mac,
            "current_ip": current_ip,
            "deco_client_name": deco_client_name,
            "vendor_name": vendor_name,
            "friendly_name": friendly_name,
            "status": status,
            "first_seen": first_seen,
            "last_seen": last_seen,
            # Include raw Deco data for reference
            "_deco_raw": deco_client,
            "_lan_raw": lan_device,
        }

        return merged_device

    def get_merged_clients(self) -> Dict[str, Any]:
        """
        Get merged view of Deco clients and LAN devices

        Returns:
            Dictionary containing:
            - merged_devices: List of correlated devices (Deco + LAN data)
            - total_merged: Count of successfully merged devices
            - unmatched_deco_clients: List of Deco clients without LAN match
            - unmatched_lan_devices: Count of LAN devices without Deco match
            - timestamp: API response timestamp
            - correlation_stats: Statistics about the correlation

        Raises:
            Exception: If data retrieval fails
        """
        try:
            logger.info("Starting correlation of Deco clients with LAN devices")

            # Fetch both sets of data
            deco_clients = self.get_deco_clients()
            lan_devices = self.get_lan_devices()

            # Correlate by MAC address
            merged_devices, unmatched_deco, unmatched_lan = self.correlate_by_mac(
                deco_clients, lan_devices
            )

            # Sort merged devices by status (online first) and then by last_seen
            merged_devices.sort(
                key=lambda x: (x["status"] != "online", x.get("last_seen", "") or "")
            )

            # Prepare response
            response = {
                "merged_devices": merged_devices,
                "total_merged": len(merged_devices),
                "unmatched_deco_clients": unmatched_deco,
                "unmatched_deco_count": len(unmatched_deco),
                "unmatched_lan_devices": len(unmatched_lan),
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_stats": {
                    "total_deco_clients": len(deco_clients),
                    "total_lan_devices": len(lan_devices),
                    "total_merged": len(merged_devices),
                    "correlation_percentage": (
                        round((len(merged_devices) / len(deco_clients) * 100), 2)
                        if deco_clients
                        else 0
                    ),
                },
            }

            logger.info(
                f"Correlation complete: {len(merged_devices)} merged, "
                f"{len(unmatched_deco)} unmatched Deco clients, "
                f"{len(unmatched_lan)} unmatched LAN devices"
            )

            return response

        except Exception as e:
            logger.error(f"Failed to get merged clients: {e}")
            raise
