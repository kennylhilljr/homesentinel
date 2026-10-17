-- HiBoost signal booster RF parameter history for tracking signal quality over time
CREATE TABLE IF NOT EXISTS hiboost_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    band TEXT NOT NULL,          -- LTE700, CELL800, PCS1900, AWS2100
    output_power_dl REAL,        -- Downlink output power in dBm
    output_power_ul REAL,        -- Uplink output power in dBm
    gain_dl REAL,                -- Downlink gain in dB
    gain_ul REAL,                -- Uplink gain in dB
    mgc_dl INTEGER DEFAULT 0,    -- Downlink MGC attenuation in dB
    mgc_ul INTEGER DEFAULT 0,    -- Uplink MGC attenuation in dB
    rf_switch INTEGER DEFAULT 1, -- RF switch on/off
    rf_status INTEGER DEFAULT 1, -- RF status normal/alert
    iso_dl INTEGER DEFAULT 1,    -- Isolation OK
    iso_ul INTEGER DEFAULT 1,
    overload_dl INTEGER DEFAULT 1,-- Overload OK
    overload_ul INTEGER DEFAULT 1,
    temperature REAL,            -- Device temperature in °C
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hiboost_history_ts ON hiboost_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_hiboost_history_band ON hiboost_history(band, timestamp);
CREATE INDEX IF NOT EXISTS idx_hiboost_history_device ON hiboost_history(device_id, timestamp);
