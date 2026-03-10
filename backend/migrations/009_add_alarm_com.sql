-- 2026-03-10: Alarm.com integration — device table for caching alarm system devices
CREATE TABLE IF NOT EXISTS alarm_com_devices (
    device_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    device_type TEXT NOT NULL,  -- partition, sensor, lock, light, thermostat, camera, garage_door, water_sensor
    state TEXT,
    mac_address TEXT,
    battery TEXT,
    malfunction INTEGER DEFAULT 0,
    raw_data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
