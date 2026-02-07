
import os
import json
import datetime
import traceback
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials missing.")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_se_record(raw_str):
    """
    Parse SE record (Horse Result) from 0B12.
    Offsets (1-based from spec, 0-based for python slice):
    HorseNum: 25-26 (idx 24-26)
    Rank: 65-66 (idx 64-66)
    """
    try:
        # Check if length is sufficient
        if len(raw_str) < 70:
            return None
        
        try:
            horse_num = int(raw_str[24:26])
        except:
            horse_num = 0
            
        rank_str = raw_str[64:66].strip()
        try:
            rank = int(rank_str)
        except:
            rank = 99 # Non-numeric rank (cancel, etc)
            
        return {
            "horse_num": horse_num,
            "rank": rank
        }
    except Exception as e:
        # print(f"SE Parse Error: {e}")
        return None

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="Target Date (YYYYMMDD)", default=None)
    args = parser.parse_args()
    
    if args.date:
        today = args.date
    else:
        today = datetime.datetime.now().strftime("%Y%m%d")

    print(f"Starting 0B12 Result Processor for Date: {today}")
    
    # 1. Fetch 0B12 data for today (2026/02/07 or target)
    
    print(f"Fetching 0B12 data for {today}...")
    res = supabase.table("raw_race_data").select("*").eq("data_type", "0B12").eq("race_date", today).execute()
    
    if not res.data:
        print("No 0B12 data found in raw_race_data. Please upload using step2_upload.py --spec 0B12.")
        return

    print(f"Found {len(res.data)} records (chunks). Processing...")
    
    # Group by Race ID
    race_map = {}
    
    for r in res.data:
        rid = r['race_id']
        content = r.get('content') # This might be just header info
        raw = r.get('raw_string')
        
        # We need to parse raw strings from the file... 
        # But wait, step2_upload.py uploads line by line?
        # Yes, usually.
        # But 'raw_string' in DB is Base64?
        # My step2_upload.py uploads `content` as JSON and `raw_string` as... wait.
        # Let's check step2_upload.py.
        # It reads line, parses ID.
        # It does NOT base64 encode by default?
        # User paste showed base64 in `raw_string`? 
        # "SFIxMj..."
        # So I might need to decode if it is base64.
        
        # Let's assume raw_string is THE string (or check if it needs decoding).
        # Actually standard step2_upload usually just puts text if utf-8.
        # But 0B12 contains Shift-JIS?
        # My downloader saves as UTF-8.
        
        # Let's proceed assuming `raw_string` is the line.
        # If it looks like base64, I might fail.
        # But I can try to parse `content` if it has it?
        # User paste content: `{"record_type": "SE"}`.
        
        # Using raw_string is safer for offsets.
        pass

    # Actually, simpler logic:
    # We iterate all rows.
    # If row is 'SE', parse Rank/Horse.
    # We aggregate winners per RaceID.
    
    race_results = {} # race_id -> {rank_1: hum, timestamp...}
    
    import base64
    
    count_se = 0
    for r in res.data:
        rid = r['race_id']
        raw_b64 = r.get('raw_string')
        if not raw_b64: continue
        
        try:
            # Try decode base64
            # Identify if it's base64?
            # User paste was base64. JRA data is binary-ish?
            # If step2 upserted it, it might be b64.
            line = base64.b64decode(raw_b64).decode('shift_jis', errors='ignore')
            # Wait, step2_upload.py reads file as UTF-8 (from downloader).
            # If downloader saved as UTF-8.
            # Then step2 upserted string.
            # Why did user paste have base64?
            # Maybe user used a DIFFERENT uploader or I am misinterpreting.
            # Let's try standard string first.
            
            line = raw_b64 # Assume plain text first?
            # But line[0] must be 'S' 'E'.
            if not line.startswith("SE"):
                # Try decode
                try:
                    line_decoded = base64.b64decode(raw_b64).decode('utf-8')
                    line = line_decoded
                except:
                    pass
        except:
            pass
            
        if line.startswith("SE"):
            data = parse_se_record(line)
            if data:
                count_se += 1
                rank = data['rank']
                hnum = data['horse_num']
                
                if rid not in race_results:
                    race_results[rid] = {"race_id": rid, "race_date": today}
                
                if rank == 1:
                    race_results[rid]["rank_1_horse_num"] = hnum
                elif rank == 2:
                    race_results[rid]["rank_2_horse_num"] = hnum
                elif rank == 3:
                    race_results[rid]["rank_3_horse_num"] = hnum

    print(f"Processed {count_se} SE records.")
    print(f"Found winners for {len(race_results)} races.")
    
    # Upsert to DB
    if race_results:
        # Convert to list
        values = list(race_results.values())
        # Upsert
        try:
            supabase.table("race_results").upsert(values).execute()
            print("Successfully updated race_results table.")
        except Exception as e:
            print(f"DB Upsert Error: {e}")
            print("Did you create the 'race_results' table? See supabase_schema.sql.")

if __name__ == "__main__":
    main()
