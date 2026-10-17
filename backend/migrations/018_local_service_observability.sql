-- Local process/service observability. Operational samples are intentionally
-- independent of device history and are pruned by LocalServiceMonitor.
CREATE TABLE IF NOT EXISTS local_service_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_local_service_events_created
    ON local_service_events(created_at DESC);

CREATE TABLE IF NOT EXISTS local_service_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    status TEXT NOT NULL,
    response_time_ms REAL,
    connection_count INTEGER NOT NULL DEFAULT 0,
    sampled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_local_service_samples_service_time
    ON local_service_samples(service_id, sampled_at DESC);

