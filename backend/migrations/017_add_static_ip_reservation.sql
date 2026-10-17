-- Migration: Add static IP reservation columns for Chester DHCP lease pinning
-- 2026-05-11: Allows users to toggle a static DHCP reservation on the Chester router
-- per device. When enabled, the device's current IP is reserved by MAC in the
-- Chester /etc/config/dhcp host table (via /api or SSH/uci fallback).
--
-- static_ip_enabled: 0 (default) = normal DHCP pool, 1 = static reservation active
-- reserved_ip:      The IP currently reserved on the router (mirrors what was written)

ALTER TABLE network_devices ADD COLUMN static_ip_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE network_devices ADD COLUMN reserved_ip TEXT DEFAULT NULL;
