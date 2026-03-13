"""
Shared utility functions for HomeSentinel backend.
# 2026-03-12: Extracted from routes/settings.py, routes/alarm_com.py, routes/alexa.py
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_setting(conn, key: str) -> Optional[str]:
    """Get a setting value from the app_settings table.

    Args:
        conn: sqlite3 connection (from db.get_connection()).
        key: Setting key string.

    Returns:
        The setting value string, or None if not found.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {e}")
        return None


def set_setting(conn, key: str, value: str) -> None:
    """Set a setting value in the app_settings table.

    Args:
        conn: sqlite3 connection (from db.get_connection()).
        key: Setting key string.
        value: Setting value string.

    Raises:
        Exception: If the database write fails.
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    conn.commit()


def normalize_mac(mac: str) -> str:
    """Normalize any MAC address format to lowercase colon-separated aa:bb:cc:dd:ee:ff.

    # 2026-03-12: Handles inputs like AA-BB-CC-DD-EE-FF, AA:BB:CC:DD:EE:FF, aabbccddeeff, etc.

    Args:
        mac: MAC address string in any common format.

    Returns:
        Normalized MAC string in aa:bb:cc:dd:ee:ff format.

    Raises:
        ValueError: If the MAC address is invalid.
    """
    if not mac:
        raise ValueError("MAC address cannot be empty")

    # Strip all non-hex characters
    hex_only = re.sub(r'[^0-9a-fA-F]', '', mac)

    if len(hex_only) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r} (expected 12 hex digits, got {len(hex_only)})")

    hex_lower = hex_only.lower()
    return ":".join(hex_lower[i:i+2] for i in range(0, 12, 2))
