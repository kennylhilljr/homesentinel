-- Alexa devices table
CREATE TABLE IF NOT EXISTS alexa_devices (
    endpoint_id TEXT PRIMARY KEY,
    friendly_name TEXT,
    description TEXT,
    manufacturer TEXT,
    model TEXT,
    device_type TEXT,
    capabilities TEXT,  -- JSON array of capability interfaces
    last_state TEXT,    -- JSON object of last known state
    state_updated_at TIMESTAMP,
    is_echo_device INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link table for Alexa device to network device correlation
CREATE TABLE IF NOT EXISTS alexa_device_links (
    alexa_endpoint_id TEXT NOT NULL,
    network_device_id TEXT NOT NULL,
    link_type TEXT DEFAULT 'auto',  -- 'auto' or 'manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (alexa_endpoint_id, network_device_id),
    FOREIGN KEY (alexa_endpoint_id) REFERENCES alexa_devices(endpoint_id),
    FOREIGN KEY (network_device_id) REFERENCES network_devices(device_id)
);
