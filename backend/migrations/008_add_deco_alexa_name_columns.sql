-- 2026-03-09: Add separate deco_name and alexa_name columns to network_devices.
-- Previously all naming sources wrote to friendly_name, losing source tracking.
-- Now Deco import -> deco_name, Alexa MAC import -> alexa_name + alexa_device_type.
-- friendly_name remains as the user's chosen/override name.
ALTER TABLE network_devices ADD COLUMN deco_name TEXT;
ALTER TABLE network_devices ADD COLUMN alexa_name TEXT;
ALTER TABLE network_devices ADD COLUMN alexa_device_type TEXT;
