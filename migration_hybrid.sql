-- Migration: Hybrid Architecture Support

-- 1. Create race_results table for scraped data
CREATE TABLE IF NOT EXISTS race_results (
    race_id TEXT PRIMARY KEY, -- YYYYMMDDJJRR
    race_date DATE NOT NULL,
    
    -- Ranking
    rank_1_horse_num INT,
    rank_2_horse_num INT,
    rank_3_horse_num INT,
    
    -- Payouts (Yen)
    pay_tan INT,           -- Win
    pay_fuku JSONB,        -- Place (List of ints)
    pay_umaren INT,        -- Quinella
    pay_umatan INT,        -- Exacta
    pay_wide JSONB,        -- Wide (List of ints)
    pay_sanrenpuku INT,    -- Trio
    pay_sanrentan INT,     -- Trifecta
    
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add approval workflow columns to bet_queue
ALTER TABLE bet_queue 
ADD COLUMN IF NOT EXISTS approved BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

-- 3. Index for performance
CREATE INDEX IF NOT EXISTS idx_race_results_date ON race_results(race_date);
