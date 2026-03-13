"""
Shared utility functions for HomeSentinel backend.
# 2026-03-12: Extracted from routes/settings.py, routes/alarm_com.py, routes/alexa.py
# 2026-03-12: Added credential encryption at rest (Fernet symmetric encryption)
"""

import os
import re
import json
import logging
from typing import Optional
from cryptography.fernet import Fernet

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


# ---------------------------------------------------------------------------
# 2026-03-12: Credential encryption at rest
# Key sourced from CREDENTIAL_KEY env var, or auto-generated and persisted
# to a .credential_key file alongside the backend code.
# ---------------------------------------------------------------------------

def _get_cipher() -> Fernet:
    """Build a Fernet cipher from env var or auto-generated key file."""
    key = os.getenv("CREDENTIAL_KEY")
    if not key:
        key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".credential_key")
        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key().decode()
            with open(key_path, "w") as f:
                f.write(key)
            os.chmod(key_path, 0o600)
    return Fernet(key.encode() if isinstance(key, str) else key)


_cipher = _get_cipher()


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string for storage."""
    return _cipher.encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a stored credential string."""
    return _cipher.decrypt(ciphertext.encode()).decode()


def store_encrypted_setting(conn, key: str, value: dict) -> None:
    """Store a dict as encrypted JSON in app_settings.

    Args:
        conn: sqlite3 connection (from db.get_connection()).
        key: Setting key string.
        value: Dict to serialize, encrypt, and store.
    """
    encrypted = encrypt_credential(json.dumps(value))
    set_setting(conn, key, encrypted)


def load_encrypted_setting(conn, key: str) -> dict | None:
    """Load and decrypt a dict from app_settings.

    Falls back to parsing as plain JSON for backwards compatibility with
    credentials stored before encryption was added.

    Args:
        conn: sqlite3 connection (from db.get_connection()).
        key: Setting key string.

    Returns:
        Decrypted dict, or None if not found.
    """
    raw = get_setting(conn, key)
    if not raw:
        return None
    # Try decrypting first; if it fails, it's probably unencrypted (pre-migration)
    try:
        decrypted = decrypt_credential(raw)
        return json.loads(decrypted)
    except Exception:
        # Fallback: try parsing as plain JSON (backwards compat)
        try:
            return json.loads(raw)
        except Exception:
            return None
