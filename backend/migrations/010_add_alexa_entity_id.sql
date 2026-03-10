-- 2026-03-10: Store Alexa entity_id on network devices for identify association
ALTER TABLE network_devices ADD COLUMN alexa_entity_id TEXT;
