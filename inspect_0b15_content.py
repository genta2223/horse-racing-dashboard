
import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    print("No URL")
    exit()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fetch all records for Tokyo 4R
rid = "2026020705010304"
print(f"Fetching all for {rid}...")
res = supabase.table("raw_race_data").select("content").eq("race_id", rid).execute()

if res.data:
    for i, r in enumerate(res.data):
        try:
            data = json.loads(r['content'])
            print(f"[{i}] Type: {data.get('record_type')} | Len: {len(r['content'])}")
            if data.get('record_type') == 'SE' and i < 5:
                 print(json.dumps(data, indent=2, ensure_ascii=False))
        except:
            print(f"[{i}] Not JSON: {r['content'][:20]}...")
else:
    print("No data found.")
