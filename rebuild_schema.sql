
-- Rebuild raw_race_data table
-- This table stores raw JV-Link data strings and their parsed content as JSONB.

DROP TABLE IF EXISTS raw_race_data;

CREATE TABLE raw_race_data (
    race_id TEXT NOT NULL,
    race_date TEXT NOT NULL,
    data_type TEXT NOT NULL, -- '0B15', '0B30', '0B12' etc.
    raw_string TEXT NOT NULL, -- Base64 encoded raw data (or direct text if possible, but safe to keep b64)
    content JSONB, -- Parsed data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, data_type, raw_string) -- Composite key to prevent exact duplicates
);

CREATE INDEX idx_raw_race_data_date ON raw_race_data(race_date);
CREATE INDEX idx_raw_race_data_type ON raw_race_data(data_type);
