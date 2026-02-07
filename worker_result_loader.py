
import os
import sys
import datetime
import traceback
import argparse
from dotenv import load_dotenv
from supabase import create_client

# Windows only
if os.name == 'nt':
    import win32com.client

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class JVResultLoader:
    def __init__(self):
        try:
            self.jv = win32com.client.Dispatch("JVDTLab.JVLink")
            self.jv.JVInit("UNKNOWN") # SID not needed for simple read
        except Exception as e:
            print(f"[ERROR] JVLink Init Failed: {e}")
            sys.exit(1)
            
        if SUPABASE_URL and SUPABASE_KEY:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        else:
            self.supabase = None
            print("[WARN] No Supabase credentials. Dry run only.")

    def parse_hr_record(self, line):
        """
        Parse HR (Refund) record from 0B12.
        Offsets (verified via debug):
        - RaceID: 11-27
        - Tan 1 Start: 102
        - Fuku 1 Start: 141
        - Slot Size: 13 bytes (Horse:2, Pay:9, Pop:2)
        """
        try:
            # RaceID
            race_id = line[11:27]
            
            # Helper to parse slot
            def parse_slot(start_idx):
                if start_idx + 13 > len(line): return None
                s = line[start_idx : start_idx+13]
                if not s.strip(): return None
                try:
                    h = int(s[0:2])
                    p = int(s[2:11])
                    return {"horse": h, "pay": p}
                except:
                    return None

            # Tan (Win) - Slot 1 only for simplicity (Handle ties later if needed)
            tan_1 = parse_slot(102)
            
            # Fuku (Place) - 5 slots max
            fuku_list = []
            for i in range(5):
                idx = 141 + (i * 13)
                f = parse_slot(idx)
                if f:
                    fuku_list.append(f)
            
            if tan_1:
                return {
                    "race_id": race_id,
                    "tan_horse": tan_1['horse'],
                    "tan_pay": tan_1['pay'],
                    "fuku_list": fuku_list
                }
            return None
        except Exception as e:
            # print(f"Parse Error: {e}")
            return None

    def run(self, target_date=None):
        if not target_date:
            target_date = datetime.datetime.now().strftime("%Y%m%d")
            
        print(f"Opening JVLink for Results (0B12) on {target_date}...")
        
        # Try JVRTOpen ("0B12")
        res = self.jv.JVRTOpen("0B12", target_date)
        method = "JVRTOpen"
        
        if res < 0:
            print(f"[INFO] JVRTOpen('0B12') returned {res}. Trying JVOpen('RACE')...")
            res = self.jv.JVOpen("RACE", target_date, 1)
            
            if isinstance(res, tuple):
                res = res[0]
            
            method = "JVOpen"
            
            if res < 0:
                print(f"[ERROR] JVOpen('RACE') failed: {res}")
                return

        print(f"[{method}] Reading Data...")
        updates = []
        
        while True:
            try:
                line_tuple = self.jv.JVRead("", 200000, "")
                if isinstance(line_tuple, tuple):
                    ret_code = line_tuple[0]
                    line = str(line_tuple[1]) if line_tuple[1] else ""
                else:
                    ret_code = line_tuple
                    line = ""
                
                if ret_code == 0: break 
                if ret_code == -1: break 
                
                if ret_code > 0:
                    line = line.strip()
                    if line.startswith("HR"):
                        data = self.parse_hr_record(line)
                        if data:
                            row = {
                                "race_id": data['race_id'],
                                "race_date": target_date,
                                "pay_tan": data['tan_pay'],
                                "rank_1_horse_num": data['tan_horse'],
                                # Explicitly clear Rank 2/3 to remove any garbage from previous processes
                                "rank_2_horse_num": None,
                                "rank_3_horse_num": None,
                                "pay_fuku": data['fuku_list'] # Supabase handles list->jsonb
                            }
                            updates.append(row)
            except Exception as e:
                print(f"Read Loop Error: {e}")
                break
                
        self.jv.JVClose()
        print(f"Processed {len(updates)} HR records.")
        
        if updates and self.supabase:
            print("Upserting to Supabase...")
            # Upsert
            chunks = [updates[i:i+50] for i in range(0, len(updates), 50)]
            for chunk in chunks:
                self.supabase.table("race_results").upsert(chunk).execute()
            print("Done.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="Target Date YYYYMMDD")
    args = parser.parse_args()
    
    loader = JVResultLoader()
    loader.run(args.date)

if __name__ == "__main__":
    main()
