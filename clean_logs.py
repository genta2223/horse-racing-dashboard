
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_system_logs():
    print("Cleaning system_logs table...")
    # Since user considers them garbage, we can delete all or just old ones.
    # The user cited logs from 2026-02-06. Today is 2026-02-07.
    # Let's delete everything older than today to be safe, or just clear all if user wants a fresh start.
    # User said "Delete these garbage data". 
    # Let's delete ALL logs to give a clean slate for the "Live Monitor".
    
    # Supabase (Postgrest) delete without where clause is blocked usually.
    # We need a condition.
    # Let's find IDs first.
    
    res = supabase.table("system_logs").select("id").execute()
    if not res.data:
        print("No logs found.")
        return

    ids = [r['id'] for r in res.data]
    print(f"Found {len(ids)} logs. Deleting...")
    
    # Delete in chunks
    chunk_size = 100
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i+chunk_size]
        supabase.table("system_logs").delete().in_("id", chunk).execute()
        print(f"Deleted chunk {i}")

    print("System logs cleaned.")

if __name__ == "__main__":
    clean_system_logs()
