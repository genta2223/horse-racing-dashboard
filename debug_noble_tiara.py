
import os
import json
import base64
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Tokyo 1R: 2026020705010301
# Horse: Noble Tiara (Umaban 05)

print("Fetching SE record for Tokyo 1R...")

res = supabase.table("raw_race_data").select("raw_string").eq("race_id", "2026020705010301").execute()

if res.data:
    for i, r in enumerate(res.data):
        raw_b64 = r['raw_string']
        try:
            raw_bytes = base64.b64decode(raw_b64)
            line = raw_bytes.decode('utf-8', errors='replace')
            
            # Check for Umaban 05 and Type SE
            # Umaban is usually around index 28 (05)
            if line.startswith("SE"):
                # rough check if it looks like Noble Tiara
                if "ノーブル" in line:
                    print(f"\n[{i}] FOUND Noble Tiara:")
                    print(line)
                    print("-" * 50)
                    ruler1 = "".join([str(i%10) for i in range(len(line))])
                    ruler2 = "".join([str(i//10) for i in range(len(line))])
                    print(ruler2)
                    print(ruler1)
                    
                    # Try to see if encoding back to shift-jis restores offsets
                    try:
                        # Attempt to reverse strict UTF-8 to Shift-JIS bytes
                        # This works only if the original decode was clean or consistent
                        # The chars "ノーブル" are Japanese.
                        
                        # Note: step1 did `str(read_res[1])`. win32com likely returned unicode.
                        # We saved that unicode as utf-8.
                        # So `line` IS that unicode string.
                        # If we encode `line` to 'shift_jis', we might get the original fixed-width byte array!
                        
                        sj_bytes = line.encode('shift_jis')
                        print("\n[Shift-JIS Byte Re-encoding]")
                        print(f"Byte Length: {len(sj_bytes)}")
                        print("Hex:", sj_bytes.hex()[:100], "...")
                        
                        # Decode specific spec offsets from the BYTES
                        # Spec (approx):
                        # Waku: offset 26 (1 byte)
                        # Umaban: offset 27 (2 bytes)
                        # HorseName: offset 34 (36 bytes)
                        # ...
                        # Weight: offset ?
                        pass
                    except Exception as e:
                        print(f"Shift-JIS encode failed: {e}")
                    
        except Exception as e:
            print(f"Error {i}: {e}")
