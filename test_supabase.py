from supabase import create_client, Client
import datetime
import sys

# User-provided Supabase Info
url: str = "https://dlhcauiwyratanbhxdnp.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRsaGNhdWl3eXJhdGFuYmh4ZG5wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAyNjA4ODIsImV4cCI6MjA4NTgzNjg4Mn0.dPmKQAv8UZfpHezwCpSLgSAKOab5c0iw-_aJt8DqML0"

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    print(f"Client Creation Error: {e}")
    sys.exit(1)

def test_insert():
    print("--- Supabase Connection Test Start ---")
    try:
        # Test Data
        test_data = {
            "race_id": "202602080101",
            "content": {
                "test_message": "Hello from 32bit Python!",
                "timestamp": str(datetime.datetime.now()),
                "status": "Success"
            }
        }
        
        # Insert Data
        response = supabase.table("raw_race_data").insert(test_data).execute()
        
        print("[OK] Data Inserted Successfully!")
        # Supabase-py v2 returns an object with .data, ensure we handle response correctly
        if hasattr(response, 'data') and len(response.data) > 0:
            print(f"Inserted ID: {response.data[0].get('id', 'Unknown')}")
        else:
            print("Response Data empty but no error raised.")
        
    except Exception as e:
        print(f"[ERROR] Insert Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_insert()
