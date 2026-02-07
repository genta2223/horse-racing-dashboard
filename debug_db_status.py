
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
# Debug Tokyo 4R (05 04R)
# 20260207 05 ?? ?? 04
# Let's search by prefix matches or just list all for date and 05/04
print("\n--- Inspecting Tokyo 4R (05 / 04R) ---")
try:
    # 0B15
    res = supabase.table("raw_race_data").select("race_id, content").eq("data_type", "0B15").eq("race_date", "20260207").execute()
    count = 0
    if res.data:
        for r in res.data:
            # Filter for Tokyo (05) and Race 04
            # ID: YYYYMMDD(8) JJ(2) KK(2) NN(2) RR(2)
            rid = r['race_id']
            if rid[8:10] == "05" and rid[14:16] == "04":
                # Print first few chars of content to identify record type (RA/SE)
                print(f"ID: {rid} | Type: {r['content'][:2]} | Len: {len(r['content'])}")
                count += 1
    print(f"Total Records for Tokyo 4R: {count}")

except Exception as e:
    print(f"Error: {e}")

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
