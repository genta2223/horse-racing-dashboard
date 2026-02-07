
import os
import json
import base64
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Tokyo 1R: Noble Tiara (Umaban 05)
# Trainer: 水野 (Mizuno)
# Jockey: 野中 (Nonaka)

print("Fetching SE record for Noble Tiara...")

res = supabase.table("raw_race_data").select("raw_string").eq("race_id", "2026020705010301").execute()

if res.data:
    for r in res.data:
        raw_b64 = r['raw_string']
        try:
            raw_bytes = base64.b64decode(raw_b64)
            line = raw_bytes.decode('utf-8', errors='replace')
            
            if "ノーブル" in line: # Found Noble Tiara
                print("Found Record!")
                
                # Convert to Shift-JIS Bytes
                try:
                    sj_bytes = line.encode('shift_jis')
                except:
                    print("Encoding failed")
                    continue
                
                # Search strings (Shift-JIS)
                targets = {
                    "Trainer (Mizuno)": "水野".encode('shift_jis'),
                    "Jockey (Nonaka)": "野中".encode('shift_jis'),
                    "Weight (Numeric?)": b'\x34\x36\x32' # 462? or maybe it's not present yet?
                }
                
                print(f"Total Bytes: {len(sj_bytes)}")
                
                for label, pattern in targets.items():
                    try:
                        idx = sj_bytes.index(pattern)
                        print(f"[{label}] Found at index: {idx}")
                        # Show surrounding bytes
                        print(f"Context [{idx-10}:{idx+20}]: {sj_bytes[idx-10:idx+20]}")
                        print(f"Decoded: {sj_bytes[idx-10:idx+20].decode('shift_jis', errors='replace')}")
                    except ValueError:
                        print(f"[{label}] NOT FOUND")
                        
                # Also dump a map of likely text fields
                print("\n--- Text Dump (10-byte chunks) ---")
                for i in range(0, len(sj_bytes), 10):
                    try:
                        chunk = sj_bytes[i:i+10]
                        decoded = chunk.decode('shift_jis', errors='replace')
                        if len(decoded.strip()) > 0:
                            print(f"{i}: {decoded}")
                    except:
                        pass
                        
        except Exception as e:
            print(e)
