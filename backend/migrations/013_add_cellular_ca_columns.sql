-- 2026-03-11: Add carrier aggregation and extended cellular columns to speed_tests.
-- Tracks CA bands, ARFCN, PCID, cell_id alongside each speedtest for band/speed correlation.
ALTER TABLE speed_tests ADD COLUMN cellular_ca_bands TEXT DEFAULT NULL;       -- JSON array of CA band strings
ALTER TABLE speed_tests ADD COLUMN cellular_ca_count INTEGER DEFAULT NULL;    -- Number of aggregated carriers
ALTER TABLE speed_tests ADD COLUMN cellular_arfcn TEXT DEFAULT NULL;          -- Primary ARFCN
ALTER TABLE speed_tests ADD COLUMN cellular_pcid TEXT DEFAULT NULL;           -- Physical Cell ID
ALTER TABLE speed_tests ADD COLUMN cellular_cell_id TEXT DEFAULT NULL;        -- Serving cell ID (hex)
ALTER TABLE speed_tests ADD COLUMN cellular_is_5g INTEGER DEFAULT NULL;      -- 1 if 5G, 0 if LTE
ALTER TABLE speed_tests ADD COLUMN cellular_mcc TEXT DEFAULT NULL;            -- Mobile Country Code
ALTER TABLE speed_tests ADD COLUMN cellular_mnc TEXT DEFAULT NULL;            -- Mobile Network Code
