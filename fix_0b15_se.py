
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
            # Decode Base64 to Raw Bytes
            raw_bytes = base64.b64decode(raw_b64)
            # Decode to UTF-8 (as preserved by step1)
            line = raw_bytes.decode('utf-8', errors='replace')
            
            # Identify Type
            if line.startswith("SE"):
                # Parse SE using Shift-JIS Bytes (Robust Method)
                try:
                    # Re-encode to Shift-JIS to restore fixed byte positions
                    sj_bytes = line.encode('shift_jis')
                except:
                    # Fallback if encoding fails
                    continue

                # Standard JRA-VAN SE Record Offsets (Bytes)
                # Waku: 27:28
                # Umaban: 28:30
                # Horse: 40:76 (36 bytes)
                # Trainer: 92:100 (8 bytes)
                # Weight: 128:131 (3 bytes)
                # Jockey: 138:146 (8 bytes)
                
                def get_sjis_str(b_data, start, end):
                    try:
                        # Decode and clean
                        return b_data[start:end].decode('shift_jis').strip().replace("\u3000", " ")
                    except:
                        return ""

                waku = get_sjis_str(sj_bytes, 27, 28)
                umaban = get_sjis_str(sj_bytes, 28, 30)
                reg_num = get_sjis_str(sj_bytes, 30, 40)
                horse_name = get_sjis_str(sj_bytes, 40, 76)
                trainer_name = get_sjis_str(sj_bytes, 92, 100)
                weight = get_sjis_str(sj_bytes, 128, 131)
                jockey_name = get_sjis_str(sj_bytes, 138, 146)
                
                # Weight Formatting
                if weight.isdigit():
                    weight = f"{int(weight)/10:.1f}"
                
                parsed = {
                    "record_type": "SE",
                    "Waku": waku,
                    "Umaban": umaban,
                    "Horse": horse_name,
                    "Jockey": jockey_name,
                    "Trainer": trainer_name,
                    "Weight": weight,
                    "RegNum": reg_num,
                    "RawString": line[:50],
                    "Odds": "---" # 0B15 does not have Odds
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
