"""
Device Search Service for HomeSentinel
Implements device search across multiple fields with MAC/IP correlation
"""

import logging
import json
from typing import List, Optional, Dict
from datetime import datetime
from db import Database

logger = logging.getLogger(__name__)


class DeviceSearchService:
    """Service for searching and filtering devices"""

    def __init__(self, db: Database):
        self.db = db

    def search(self, query: str, status_filter: Optional[str] = None) -> List[dict]:
        """
        Search for devices across multiple fields.

        Searches across:
        - MAC address (prefix match)
        - IP address (substring match)
        - Hostname (contains match)
        - Friendly name (contains match)
        - Vendor name (contains match)

        Args:
            query: Search query string
            status_filter: Optional status filter ('online', 'offline')

        Returns:
            List of matching devices
        """
        if not query or not query.strip():
            return []

        query_lower = query.lower().strip()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Build the SQL query
                sql = """
                    SELECT * FROM network_devices
                    WHERE (
                        LOWER(mac_address) LIKE ?
                        OR LOWER(current_ip) LIKE ?
                        OR LOWER(hostname) LIKE ?
                        OR LOWER(friendly_name) LIKE ?
                        OR LOWER(vendor_name) LIKE ?
                    )
                """
                params = [
                    f"{query_lower}%",  # MAC prefix match
                    f"%{query_lower}%",  # IP substring match
                    f"%{query_lower}%",  # Hostname contains
                    f"%{query_lower}%",  # Friendly name contains
                    f"%{query_lower}%"   # Vendor name contains
                ]

                # Add status filter if provided
                if status_filter:
                    sql += " AND status = ?"
                    params.append(status_filter)

                sql += " ORDER BY last_seen DESC"

                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [self._enrich_device(dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def search_by_mac_prefix(self, mac_prefix: str, status_filter: Optional[str] = None) -> List[dict]:
        """Search for devices by MAC address prefix"""
        return self.search(mac_prefix, status_filter)

    def search_by_ip(self, ip_query: str, status_filter: Optional[str] = None) -> List[dict]:
        """Search for devices by IP address"""
        return self.search(ip_query, status_filter)

    def search_by_hostname(self, hostname_query: str, status_filter: Optional[str] = None) -> List[dict]:
        """Search for devices by hostname"""
        return self.search(hostname_query, status_filter)

    def search_by_friendly_name(self, name_query: str, status_filter: Optional[str] = None) -> List[dict]:
        """Search for devices by friendly name"""
        return self.search(name_query, status_filter)

    def search_by_vendor(self, vendor_query: str, status_filter: Optional[str] = None) -> List[dict]:
        """Search for devices by vendor name"""
        return self.search(vendor_query, status_filter)

    def _enrich_device(self, device: dict) -> dict:
        """Enrich device dict with parsed IP history"""
        if device.get('ip_history'):
            try:
                device['ip_history'] = json.loads(device['ip_history'])
            except (json.JSONDecodeError, TypeError):
                device['ip_history'] = []
        else:
            device['ip_history'] = []
        return device

    def update_ip_history(self, device_id: str, new_ip: str) -> bool:
        """
        Update IP history when device IP changes.

        Args:
            device_id: Device ID
            new_ip: New IP address

        Returns:
            True if updated, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Get current device
                cursor.execute(
                    "SELECT current_ip, ip_history FROM network_devices WHERE device_id = ?",
                    (device_id,)
                )
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"Device not found: {device_id}")
                    return False

                current_ip = row[0]
                ip_history_json = row[1]

                # Parse existing history
                ip_history = []
                if ip_history_json:
                    try:
                        ip_history = json.loads(ip_history_json)
                    except (json.JSONDecodeError, TypeError):
                        ip_history = []

                # Only update if IP actually changed
                if current_ip != new_ip and new_ip:
                    # Add current IP to history
                    if current_ip:
                        ip_history.append({
                            'ip': current_ip,
                            'seen_at': datetime.utcnow().isoformat()
                        })

                    # Update device with new IP and updated history
                    new_history_json = json.dumps(ip_history)
                    cursor.execute("""
                        UPDATE network_devices
                        SET current_ip = ?, ip_history = ?, ip_history_updated_at = ?, updated_at = ?
                        WHERE device_id = ?
                    """, (new_ip, new_history_json, datetime.utcnow(), datetime.utcnow(), device_id))

                    conn.commit()
                    logger.info(f"Updated IP history for {device_id}: {current_ip} -> {new_ip}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Failed to update IP history: {e}")
            return False

    def get_device_ip_history(self, device_id: str) -> List[dict]:
        """Get IP history for a device"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT ip_history, current_ip FROM network_devices WHERE device_id = ?",
                    (device_id,)
                )
                row = cursor.fetchone()

                if not row:
                    return []

                ip_history_json = row[0]
                current_ip = row[1]

                # Parse history
                ip_history = []
                if ip_history_json:
                    try:
                        ip_history = json.loads(ip_history_json)
                    except (json.JSONDecodeError, TypeError):
                        ip_history = []

                # Add current IP as most recent
                if current_ip:
                    ip_history.append({
                        'ip': current_ip,
                        'seen_at': datetime.utcnow().isoformat(),
                        'current': True
                    })

                return ip_history

        except Exception as e:
            logger.error(f"Failed to get IP history: {e}")
            return []
