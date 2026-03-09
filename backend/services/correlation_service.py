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
    Matches devices by MAC address to provide unified view of network.
    Also supports Alexa device correlation.
    """

    def __init__(self, deco_service: DecoService, device_repo: NetworkDeviceRepository,
                 alexa_service=None, db=None):
        """
        Initialize correlation service

        Args:
            deco_service: DecoService instance for fetching Deco clients
            device_repo: NetworkDeviceRepository for accessing local device data
            alexa_service: Optional AlexaService for Alexa device correlation
            db: Optional Database instance for reading link table
        """
        self.deco_service = deco_service
        self.device_repo = device_repo
        self.alexa_service = alexa_service
        self.db = db

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

    def get_alexa_links(self) -> List[Dict[str, Any]]:
        """Get all Alexa-to-network device links from database"""
        if not self.db:
            return []
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT al.alexa_endpoint_id, al.network_device_id, al.link_type,
                           ad.friendly_name as alexa_name, ad.device_type as alexa_type,
                           nd.mac_address, nd.current_ip, nd.friendly_name as network_name
                    FROM alexa_device_links al
                    LEFT JOIN alexa_devices ad ON al.alexa_endpoint_id = ad.endpoint_id
                    LEFT JOIN network_devices nd ON al.network_device_id = nd.device_id
                """)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get Alexa links: {e}")
            return []

    def auto_correlate_alexa(self) -> Dict[str, Any]:
        """
        Auto-correlate Alexa devices with network devices by matching IP addresses.
        This is best-effort since Alexa doesn't always expose MAC/IP.
        """
        if not self.alexa_service or not self.db:
            return {"linked": 0, "message": "Alexa service or DB not available"}

        try:
            alexa_devices = self.alexa_service.get_devices()
            lan_devices = self.get_lan_devices()
            linked_count = 0

            # Build IP-to-device map for LAN devices
            ip_to_device = {}
            for d in lan_devices:
                ip = d.get("current_ip", "")
                if ip:
                    ip_to_device[ip] = d

            # Try to match Alexa devices by any available network info
            for alexa_dev in alexa_devices:
                endpoint_id = alexa_dev.get("endpoint_id", "")
                raw = alexa_dev.get("raw_data", {})

                # Some Alexa devices expose network info in additionalAttributes
                network_info = raw.get("additionalAttributes", {})
                device_ip = network_info.get("ipAddress") or network_info.get("ip_address")

                if device_ip and device_ip in ip_to_device:
                    lan_dev = ip_to_device[device_ip]
                    device_id = lan_dev.get("device_id", "")

                    with self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT OR IGNORE INTO alexa_device_links (alexa_endpoint_id, network_device_id, link_type) VALUES (?, ?, 'auto')",
                            (endpoint_id, device_id),
                        )
                        conn.commit()
                        if cursor.rowcount > 0:
                            linked_count += 1

            return {"linked": linked_count, "message": f"Auto-linked {linked_count} devices"}
        except Exception as e:
            logger.error(f"Auto-correlation failed: {e}")
            return {"linked": 0, "message": f"Error: {e}"}

    def sync_network_friendly_names_from_alexa(self, overwrite_existing: bool = False) -> Dict[str, Any]:
        """
        Copy linked Alexa device names into network device friendly names.

        Args:
            overwrite_existing: When False, keeps existing non-empty network friendly names.

        Returns:
            Summary with updated/skipped/failed counts.
        """
        links = self.get_alexa_links()
        if not links:
            return {
                "success": True,
                "updated": 0,
                "skipped_existing": 0,
                "skipped_missing": 0,
                "failed": 0,
                "message": "No Alexa links found",
            }

        updated = 0
        skipped_existing = 0
        skipped_missing = 0
        failed = 0
        updates: List[Dict[str, str]] = []

        for link in links:
            network_device_id = (link.get("network_device_id") or "").strip()
            alexa_name = (link.get("alexa_name") or "").strip()
            network_name = (link.get("network_name") or "").strip()

            if not network_device_id or not alexa_name:
                skipped_missing += 1
                continue

            if not overwrite_existing and network_name:
                skipped_existing += 1
                continue

            if network_name == alexa_name:
                skipped_existing += 1
                continue

            try:
                result = self.device_repo.update_device_metadata(
                    network_device_id, friendly_name=alexa_name
                )
                if result:
                    updated += 1
                    updates.append({
                        "network_device_id": network_device_id,
                        "new_name": alexa_name,
                    })
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.error(
                    "Failed to sync friendly name for network device %s: %s",
                    network_device_id,
                    e,
                )

        return {
            "success": True,
            "updated": updated,
            "skipped_existing": skipped_existing,
            "skipped_missing": skipped_missing,
            "failed": failed,
            "total_links": len(links),
            "updates": updates,
        }
