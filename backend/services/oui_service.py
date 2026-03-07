"""
OUI Service for HomeSentinel
Implements OUI (Organizationally Unique Identifier) lookup for MAC address vendor identification
"""

import csv
import os
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class OUIService:
    """Service for OUI database lookups"""

    def __init__(self, oui_csv_path: Optional[str] = None):
        """Initialize OUI service with database file"""
        if oui_csv_path is None:
            # Default path relative to backend/data
            script_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(script_dir)
            oui_csv_path = os.path.join(backend_dir, "data", "oui_database.csv")

        self.oui_csv_path = oui_csv_path
        self.oui_database: Dict[str, str] = {}
        self.cache: Dict[str, str] = {}
        self._load_database()

    def _load_database(self) -> None:
        """Load OUI database from CSV file"""
        try:
            if not os.path.exists(self.oui_csv_path):
                logger.warning(f"OUI database file not found: {self.oui_csv_path}")
                return

            with open(self.oui_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row and 'OUI' in row and 'COMPANY' in row:
                        # Normalize OUI to uppercase without colons
                        oui = row['OUI'].strip().upper().replace(':', '').replace('-', '')
                        company = row['COMPANY'].strip()
                        # Only add if not already present (keep first occurrence)
                        if oui not in self.oui_database:
                            self.oui_database[oui] = company

            logger.info(f"OUI database loaded successfully: {len(self.oui_database)} entries")

        except Exception as e:
            logger.error(f"Failed to load OUI database: {e}")

    def lookup_vendor(self, mac_address: str) -> str:
        """
        Lookup vendor name by MAC address

        Args:
            mac_address: MAC address in format "AA:BB:CC:DD:EE:FF" or "AABBCCDDEE:FF"

        Returns:
            Vendor name or "Unknown Vendor" if not found
        """
        # Normalize MAC address
        normalized_mac = self._normalize_mac(mac_address)
        if not normalized_mac:
            return "Unknown Vendor"

        # Check cache first
        if normalized_mac in self.cache:
            return self.cache[normalized_mac]

        # Extract OUI prefix (first 6 characters)
        oui_prefix = normalized_mac[:6].upper()

        # Look up in database
        vendor = self.oui_database.get(oui_prefix, "Unknown Vendor")

        # Cache the result
        self.cache[normalized_mac] = vendor

        return vendor

    def _normalize_mac(self, mac_address: str) -> Optional[str]:
        """
        Normalize MAC address to format without separators

        Args:
            mac_address: MAC address in various formats

        Returns:
            Normalized MAC address or None if invalid
        """
        if not mac_address:
            return None

        # Remove common separators
        normalized = mac_address.replace(':', '').replace('-', '').replace('.', '')

        # Ensure it's 12 hex characters
        if len(normalized) != 12:
            return None

        # Check if all characters are hex
        try:
            int(normalized, 16)
            return normalized
        except ValueError:
            return None

    def lookup_vendor_cached(self, mac_address: str) -> str:
        """
        Lookup vendor name by MAC address with caching

        Args:
            mac_address: MAC address

        Returns:
            Vendor name from cache or database
        """
        return self.lookup_vendor(mac_address)

    def get_database_size(self) -> int:
        """Get number of OUI entries loaded"""
        return len(self.oui_database)

    def get_cache_size(self) -> int:
        """Get number of cached lookups"""
        return len(self.cache)

    def clear_cache(self) -> None:
        """Clear lookup cache"""
        self.cache.clear()
        logger.info("OUI lookup cache cleared")

    def reload_database(self) -> None:
        """Reload OUI database from file"""
        self.oui_database.clear()
        self.cache.clear()
        self._load_database()
        logger.info("OUI database reloaded")
