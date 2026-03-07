-- Migration: Initialize NetworkDevice table
-- Purpose: Create the database schema for network device discovery and tracking

CREATE TABLE IF NOT EXISTS network_devices (
    device_id TEXT PRIMARY KEY,
    mac_address TEXT NOT NULL UNIQUE,
    current_ip TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'online' CHECK(status IN ('online', 'offline', 'unknown')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_mac_address ON network_devices(mac_address);
CREATE INDEX IF NOT EXISTS idx_current_ip ON network_devices(current_ip);
CREATE INDEX IF NOT EXISTS idx_status ON network_devices(status);
CREATE INDEX IF NOT EXISTS idx_last_seen ON network_devices(last_seen);

-- Create polling configuration table
CREATE TABLE IF NOT EXISTS polling_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    polling_interval_seconds INTEGER DEFAULT 60 CHECK(polling_interval_seconds > 0),
    last_scan_timestamp TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize polling config with defaults
INSERT OR IGNORE INTO polling_config (id, polling_interval_seconds)
VALUES (1, 60);
