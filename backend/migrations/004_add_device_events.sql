-- Migration: Add device events and alerts tables
-- Purpose: Track device connection/disconnection events and generate alerts for new devices

-- Create device_events table for tracking all device-related events
CREATE TABLE IF NOT EXISTS device_events (
    event_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('connected', 'disconnected', 'online', 'offline', 'new_device')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES network_devices(device_id) ON DELETE CASCADE
);

-- Create indexes for efficient filtering
CREATE INDEX IF NOT EXISTS idx_device_events_device_id ON device_events(device_id);
CREATE INDEX IF NOT EXISTS idx_device_events_timestamp ON device_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_device_events_type ON device_events(event_type);
CREATE INDEX IF NOT EXISTS idx_device_events_created_at ON device_events(created_at);

-- Create device_alerts table for tracking dismissible alerts
CREATE TABLE IF NOT EXISTS device_alerts (
    alert_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    alert_type TEXT NOT NULL CHECK(alert_type IN ('new_device', 'device_reconnected', 'device_offline')),
    dismissed INTEGER DEFAULT 0,
    dismissed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES network_devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES device_events(event_id) ON DELETE CASCADE
);

-- Create indexes for alerts
CREATE INDEX IF NOT EXISTS idx_device_alerts_device_id ON device_alerts(device_id);
CREATE INDEX IF NOT EXISTS idx_device_alerts_dismissed ON device_alerts(dismissed);
CREATE INDEX IF NOT EXISTS idx_device_alerts_created_at ON device_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_device_alerts_alert_type ON device_alerts(alert_type);
