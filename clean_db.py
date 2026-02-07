
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_garbage():
    print("Deleting garbage entries (race_id not starting with '20')...")
    # Delete anything that doesn't look like a year-based ID
    # Note: 'not_.ilike' support might be limited in py-supabase, looping might be safer but slow.
    # Let's try direct delete logic if possible.
    # Supabase-py uses postgrest.
    
    # Logic: Delete where race_date = '20260207' AND race_id NOT like '20%'
    today = "20260207"
    
    # 1. Fetch bad IDs to verify
    res = supabase.table("raw_race_data").select("race_id").eq("race_date", today).not_.ilike("race_id", "2026%").execute()
    bad_ids = [r['race_id'] for r in res.data] if res.data else []
    
    print(f"Found {len(bad_ids)} bad IDs for {today}.")
    if bad_ids:
        # Delete in chunks
        chunk_size = 100
        for i in range(0, len(bad_ids), chunk_size):
            chunk = bad_ids[i:i+chunk_size]
            supabase.table("raw_race_data").delete().in_("race_id", chunk).execute()
            print(f"Deleted chunk {i}")
            
    # Also check 20260208
    tomorrow = "20260208"
    res_tm = supabase.table("raw_race_data").select("race_id").eq("race_date", tomorrow).not_.ilike("race_id", "2026%").execute()
    bad_ids_tm = [r['race_id'] for r in res_tm.data] if res_tm.data else []
    print(f"Found {len(bad_ids_tm)} bad IDs for {tomorrow}.")
    if bad_ids_tm:
        for i in range(0, len(bad_ids_tm), chunk_size):
            chunk = bad_ids_tm[i:i+chunk_size]
            supabase.table("raw_race_data").delete().in_("race_id", chunk).execute()
            print(f"Deleted chunk {i}")

    print("Cleanup Complete.")

if __name__ == "__main__":
    clean_garbage()
