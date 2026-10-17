-- Add mac_address column to alexa_devices for Endpoint API v2 connection data
-- MAC addresses come from the Alexa Endpoint API connections[].macAddress field
ALTER TABLE alexa_devices ADD COLUMN mac_address TEXT;
