-- Migration: Add preferred Deco node column for connection pinning
-- 2026-03-11: Allows users to pin a device to a specific Deco node
-- NULL = auto (device connects to whichever node it wants)
-- A MAC value = pinned to that specific Deco node

ALTER TABLE network_devices ADD COLUMN preferred_deco_node TEXT DEFAULT NULL;
