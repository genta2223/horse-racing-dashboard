
import os
import json
import base64
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fetch one SE record for Tokyo 4R
# race_id for Tokyo 4R: 2026020705010304
# We want record_type SE.
# Since we haven't fixed the content yet, we check the raw string.
print("Fetching SE record for Tokyo 4R...")

# Helper to identify if a record is SE
def is_se(raw_text):
    return raw_text.startswith("SE")

# Get all records for the race
res = supabase.table("raw_race_data").select("raw_string").eq("race_id", "2026020705010304").execute()

found = False
if res.data:
    for r in res.data:
        raw_b64 = r['raw_string']
        try:
            raw_bytes = base64.b64decode(raw_b64)
            # Try decode as utf-8 (since step1 saved as utf-8)
            raw_text = raw_bytes.decode('utf-8')
            
            if raw_text.startswith("SE"):
                found = True
                print("\n=== Found SE Record ===")
                print(raw_text)
                print("-" * 50)
                # Print with index ruler
                ruler1 = "".join([str(i%10) for i in range(len(raw_text))])
                ruler2 = "".join([str(i//10) for i in range(len(raw_text))])
                print(ruler2)
                print(ruler1)
                break
        except Exception as e:
            print(f"Decode error: {e}")

if not found:
    print("No SE record found.")
