-- 2026-03-12: Add 'seen' column to device_alerts for browser push notification tracking.
-- Alerts start as unseen (0). After a browser notification fires, they are marked seen (1).
ALTER TABLE device_alerts ADD COLUMN seen INTEGER DEFAULT 0;
