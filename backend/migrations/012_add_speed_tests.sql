-- 2026-03-11: Speed test results table for tracking internet performance over time
CREATE TABLE IF NOT EXISTS speed_tests (
    test_id TEXT PRIMARY KEY,
    download_mbps REAL NOT NULL,
    upload_mbps REAL NOT NULL,
    ping_ms REAL NOT NULL,
    jitter_ms REAL DEFAULT NULL,
    server_name TEXT DEFAULT NULL,
    server_id TEXT DEFAULT NULL,
    server_host TEXT DEFAULT NULL,
    isp TEXT DEFAULT NULL,
    external_ip TEXT DEFAULT NULL,
    -- Chester cellular snapshot at time of test
    cellular_band TEXT DEFAULT NULL,
    cellular_rsrp REAL DEFAULT NULL,
    cellular_rsrq REAL DEFAULT NULL,
    cellular_sinr REAL DEFAULT NULL,
    cellular_connection_type TEXT DEFAULT NULL,
    -- Metadata
    bytes_sent INTEGER DEFAULT NULL,
    bytes_received INTEGER DEFAULT NULL,
    test_duration_seconds REAL DEFAULT NULL,
    error TEXT DEFAULT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_speed_tests_timestamp ON speed_tests(timestamp);

-- AI insights table for storing GenAI analysis of speed test patterns
CREATE TABLE IF NOT EXISTS speed_insights (
    insight_id TEXT PRIMARY KEY,
    insight_type TEXT NOT NULL,  -- 'hourly_pattern', 'anomaly', 'trend', 'recommendation'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    data_json TEXT DEFAULT NULL,  -- supporting data/metrics
    confidence REAL DEFAULT NULL,  -- 0.0-1.0
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_speed_insights_type ON speed_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_speed_insights_created ON speed_insights(created_at);
