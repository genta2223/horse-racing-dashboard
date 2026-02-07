
import os
import json
import base64
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DATE_TARGET = "20260207"

print(f"Fixing SE records for {DATE_TARGET}...")

# Fetch all 0B15 records
res = supabase.table("raw_race_data").select("*").eq("data_type", "0B15").eq("race_date", DATE_TARGET).execute()

updates = 0
if res.data:
    for r in res.data:
        rid = r['race_id']
        raw_b64 = r['raw_string']
        
        try:
            # Decode
            raw_bytes = base64.b64decode(raw_b64)
            line = raw_bytes.decode('utf-8', errors='replace')
            
            # Identify Type
            if line.startswith("SE"):
                # Parse SE
                # Adjusted Offsets (based on user feedback -6 chars from previous)
                
                # Waku: 27 (1 char)
                # Umaban: 28:30 (2 chars)
                # RegNum: 30:40 (10 chars)
                # Horse: 40:58 (18 chars)
                # Weight: 128:131
                # Jockey: 144:160
                
                waku = line[27:28] if len(line) > 27 else ""
                umaban = line[28:30].strip()
                reg_num = line[30:40].strip()
                horse_name = line[40:58].strip().replace("@", " ").replace(" ", "") 
                
                weight = line[128:131].strip()
                jockey_name = line[144:160].strip().replace("@", " ").replace(" ", "")
                
                parsed = {
                    "record_type": "SE",
                    "Waku": waku,
                    "Umaban": umaban,
                    "Horse": horse_name,
                    "Jockey": jockey_name,
                    "Weight": f"{int(weight)/10:.1f}" if weight.isdigit() else weight,
                    "RegNum": reg_num,
                    "RawString": line[:50]
                }
                
                # Update DB
                supabase.table("raw_race_data").update({"content": json.dumps(parsed, ensure_ascii=False)}).eq("race_id", rid).eq("raw_string", raw_b64).execute()
                updates += 1
                if updates % 10 == 0:
                    print(f"Updates: {updates}", end="\r")
                
            elif line.startswith("RA"):
                # Parse RA (Basic)
                parsed = {
                    "record_type": "RA",
                    "RaceName": "Race Name",
                    "Track": "Track"
                }
                supabase.table("raw_race_data").update({"content": json.dumps(parsed, ensure_ascii=False)}).eq("race_id", rid).eq("raw_string", raw_b64).execute()
                updates += 1
                
        except Exception as e:
            # print(f"Error {rid}: {e}")
            pass

print(f"\nCreate {updates} updates.")
