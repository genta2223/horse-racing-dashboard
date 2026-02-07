
import os
import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_db():
    today = "20260207"
    
    # 1. Check raw_race_data for 0B15 with valid ID format
    print(f"--- Checking 0B15 for {today} (Valid IDs) ---")
    res = supabase.table("raw_race_data").select("race_id").eq("race_date", today).ilike("race_id", "2026%").limit(5).execute()
    if res.data:
        print(f"Found {len(res.data)} VALID 0B15 records.")
        for r in res.data:
            print(f"Valid ID: {r['race_id']}")
    else:
        print("NO VALID (2026...) 0B15 DATA FOUND.")

    # Check for garbage IDs
    res_bad = supabase.table("raw_race_data").select("race_id").eq("race_date", today).not_.ilike("race_id", "2026%").limit(5).execute()
    if res_bad.data:
         print(f"Found {len(res_bad.data)} GARBAGE records (e.g. {res_bad.data[0]['race_id']})")

    # 2. Check bet_queue
    print(f"\n--- Checking Bet Queue ---")
    # Correct column is created_at
    res_bets = supabase.table("bet_queue").select("race_id, created_at").limit(5).execute()
    if res_bets.data:
        for b in res_bets.data:
            # Check if race_id is valid
            print(f"Bet RaceID: {b['race_id']}")
    else:
        print("NO BETS FOUND.")

    # 3. Check race_results
    print(f"\n--- Checking Results ---")
    res_res = supabase.table("race_results").select("*").limit(5).execute()
    if res_res.data:
        print(f"Found {len(res_res.data)} results.")
    else:
        print("NO RESULTS FOUND.")

if __name__ == "__main__":
    check_db()
