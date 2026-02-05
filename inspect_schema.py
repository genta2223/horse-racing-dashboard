from supabase import create_client, Client
import sys
import json

url: str = "https://dlhcauiwyratanbhxdnp.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRsaGNhdWl3eXJhdGFuYmh4ZG5wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAyNjA4ODIsImV4cCI6MjA4NTgzNjg4Mn0.dPmKQAv8UZfpHezwCpSLgSAKOab5c0iw-_aJt8DqML0"

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    print(f"Client Creation Error: {e}")
    sys.exit(1)

def inspect():
    print("--- Inspecting Schema ---")
    try:
        # Try to select everything from a single row
        response = supabase.table("raw_race_data").select("*").limit(1).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            row = response.data[0]
            print("Row keys:", list(row.keys()))
            print("Full Row:", json.dumps(row, indent=2))
        else:
            print("Table empty. Cannot infer schema from data.")
            # If empty, try to insert a minimal row knowing 'race_id' usually exists.
            # But we failed to insert because of extra columns.
            pass
            
    except Exception as e:
        print(f"Inspection Failed: {e}")

if __name__ == "__main__":
    inspect()
