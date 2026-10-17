-- Migration: Add IP history tracking
-- Purpose: Track IP address changes over time for devices

-- Add new columns to network_devices table
ALTER TABLE network_devices ADD COLUMN hostname TEXT;
ALTER TABLE network_devices ADD COLUMN ip_history TEXT;
ALTER TABLE network_devices ADD COLUMN ip_history_updated_at TIMESTAMP;

-- Create indexes for faster searches
CREATE INDEX IF NOT EXISTS idx_hostname ON network_devices(hostname);
CREATE INDEX IF NOT EXISTS idx_friendly_name ON network_devices(friendly_name);
