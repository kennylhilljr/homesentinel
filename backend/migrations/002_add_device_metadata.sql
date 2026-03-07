-- Migration: Add device metadata and device groups
-- Purpose: Add vendor lookup, device metadata, and device grouping support

-- Add new columns to network_devices table
ALTER TABLE network_devices ADD COLUMN friendly_name TEXT;
ALTER TABLE network_devices ADD COLUMN device_type TEXT DEFAULT 'unknown';
ALTER TABLE network_devices ADD COLUMN vendor_name TEXT;
ALTER TABLE network_devices ADD COLUMN notes TEXT;

-- Create device_groups table
CREATE TABLE IF NOT EXISTS device_groups (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#3498db',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster group lookups
CREATE INDEX IF NOT EXISTS idx_group_name ON device_groups(name);

-- Create device_group_members table for membership
CREATE TABLE IF NOT EXISTS device_group_members (
    group_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, device_id),
    FOREIGN KEY (group_id) REFERENCES device_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES network_devices(device_id) ON DELETE CASCADE
);

-- Create index for faster member lookups
CREATE INDEX IF NOT EXISTS idx_device_group_members_device_id ON device_group_members(device_id);
CREATE INDEX IF NOT EXISTS idx_device_group_members_group_id ON device_group_members(group_id);
