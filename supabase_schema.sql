-- ============================================
-- Supabase Table: raw_race_data
-- ============================================
-- Purpose: Store JRA race data uploaded from local PC via JV-Link
-- 
-- Usage:
--   1. Copy this SQL
--   2. Go to Supabase Dashboard > SQL Editor
--   3. Paste and Run
-- ============================================

-- ===== OPTION A: If table does NOT exist (fresh setup) =====
-- Uncomment and run this block:

/*
CREATE TABLE raw_race_data (
    id BIGSERIAL PRIMARY KEY,
    race_id TEXT NOT NULL,
    data_type TEXT NOT NULL,
    race_date TEXT,
    content JSONB,
    raw_string TEXT,
    status TEXT DEFAULT 'pending',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, data_type)
);
*/

-- ===== OPTION B: If table already exists (migration) =====
-- Run these ALTER statements to add missing columns:

-- Add race_date column if missing
ALTER TABLE raw_race_data 
ADD COLUMN IF NOT EXISTS race_date TEXT;

-- Add content column if missing (JSONB for parsed data)
ALTER TABLE raw_race_data 
ADD COLUMN IF NOT EXISTS content JSONB;

-- Add raw_string column if missing
ALTER TABLE raw_race_data 
ADD COLUMN IF NOT EXISTS raw_string TEXT;

-- Add status column if missing
ALTER TABLE raw_race_data 
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

-- Update unique constraint (if needed)
-- Note: This may fail if constraint already exists - that's OK
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'raw_race_data_race_id_data_type_key'
    ) THEN
        ALTER TABLE raw_race_data 
        ADD CONSTRAINT raw_race_data_race_id_data_type_key 
        UNIQUE(race_id, data_type);
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Constraint may already exist, skipping...';
END $$;

-- Create indexes (IF NOT EXISTS handles duplicates)
CREATE INDEX IF NOT EXISTS idx_raw_race_data_date 
    ON raw_race_data(race_date);
CREATE INDEX IF NOT EXISTS idx_raw_race_data_type 
    ON raw_race_data(data_type);
CREATE INDEX IF NOT EXISTS idx_raw_race_data_timestamp 
    ON raw_race_data(timestamp DESC);

-- ============================================
-- Verification: Check table structure
-- ============================================
-- Run this to verify the table:
-- SELECT column_name, data_type FROM information_schema.columns 
-- WHERE table_name = 'raw_race_data';

COMMENT ON TABLE raw_race_data IS 'JRA race data from JV-Link, uploaded by local collector';

-- ============================================
-- Supabase Table: race_results
-- ============================================
-- Purpose: Store scraped race results from netkeiba/JRA website
CREATE TABLE IF NOT EXISTS race_results (
    race_id TEXT PRIMARY KEY,
    race_date TEXT,
    rank_1_horse_num INTEGER,
    rank_2_horse_num INTEGER,
    rank_3_horse_num INTEGER,
    pay_tan INTEGER,            -- Win Payout (yen)
    pay_fuku JSONB,             -- Place Payouts (list)
    pay_umaren INTEGER,         -- Quinella
    pay_umatan INTEGER,         -- Exacta
    pay_wide JSONB,             -- Wide Payouts (list)
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE race_results IS 'Scraped race results for verification';

