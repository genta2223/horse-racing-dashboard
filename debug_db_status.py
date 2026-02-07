
import os
import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Missing keys")
    exit()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print(f"\n--- Checking Race 2026020705010302 ---")
try:
    res = supabase.table("race_results").select("*").eq("race_id", "2026020705010302").execute()
    if res.data:
        print(res.data)
    else:
        print("Record not found.")
        
    print(f"\n--- Checking Race 2026020705010303 ---")
    res = supabase.table("race_results").select("*").eq("race_id", "2026020705010303").execute()
    if res.data:
        print(res.data)
    else:
        print("Record not found.")

except Exception as e:
    print(f"Error: {e}")
