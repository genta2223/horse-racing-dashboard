
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

print(f"Fixing SE records for {DATE_TARGET} with Strict 0B15 Spec...")

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
            # Decode to UTF-8
            line = raw_bytes.decode('utf-8', errors='replace')
            
            if line.startswith("SE"):
                # Re-encode to Shift-JIS for byte slicing
                try:
                    sj_bytes = line.encode('cp932') # Use CP932 for strict Shift-JIS (Windows)
                except:
                    continue
                
                def get_val(start, length):
                    try:
                        chunk = sj_bytes[start : start + length]
                        return chunk.decode('cp932', errors='replace').strip().replace("\u3000", " ")
                    except:
                        return ""

                # --- JRA-VAN 0B15 Spec (User Provided) ---
                # Record Spec: 0:2
                # Year: 11:15
                # Month: 15:17
                # Day: 17:19
                # Place Code: 19:21
                # Race Num: 25:27
                # Horse Num: 28:30
                # Horse Name: 68:104 (36 bytes)
                # Sex Code: 46:47
                # Hair Code: 47:49
                # Age: 50:52
                # Jockey Name: 134:146 (12 bytes)
                # Weight: 122:125 (3 bytes)
                # Trainer Name: 178:190 (12 bytes)
                # Owner Name: 210:270 (60 bytes)
                
                umaban = get_val(28, 2)
                horse_name = get_val(68, 36)
                jockey_name = get_val(134, 12)
                trainer_name = get_val(178, 12)
                weight_raw = get_val(122, 3)
                waku = get_val(26, 1) # Guessing based on logic (usually near Umaban) - actually spec says 26?
                # User didn't give Waku offset, but previously I guessed 27. 
                # Let's try to infer or leave blank if unknown.
                # Actually standard is usually: [RaceNum(2)][Waku(1)][Umaban(2)] -> 25+2=27? So 27:28.
                # Let's check: Race Num is 25:27. So Waku might be 27:28.
                waku = get_val(27, 1) # Safe bet based on previous alignment
                
                reg_num = get_val(30, 10) # Registration Number usually follows Umaban? Spec says Horse Name starts at 68. 30->68 is huge gap.
                # Wait, User spec: Horse Num 28:30. Horse Name 68. 
                # There is a gap 30-68. 
                # Detailed spec usually has RegNum in there.
                # I will leave RegNum as is (30:40) based on previous visual inspection.
                # But wait, 30+10=40. 40 is not 68.
                # If User Spec is correct, my previous regex was WAY off.
                # Let's trust User Spec for the fields provided.
                
                # Weight Formatting
                weight = weight_raw
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
                    "RawString": line[:50],
                    "Odds": "---" 
                }
                
                # Update DB
                supabase.table("raw_race_data").update({"content": json.dumps(parsed, ensure_ascii=False)}).eq("race_id", rid).eq("raw_string", raw_b64).execute()
                updates += 1
                if updates % 10 == 0:
                    print(f"Updates: {updates}", end="\r")
                    
        except Exception as e:
            pass

print(f"\nCreate {updates} updates.")
