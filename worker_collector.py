import win32com.client
from supabase import create_client, Client
import datetime
import time
import sys

# --- Config ---
SUPABASE_URL = "https://dlhcauiwyratanbhxdnp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRsaGNhdWl3eXJhdGFuYmh4ZG5wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAyNjA4ODIsImV4cCI6MjA4NTgzNjg4Mn0.dPmKQAv8UZfpHezwCpSLgSAKOab5c0iw-_aJt8DqML0"

# Target Dates (Upcoming Weekend)
TARGET_DATES = [
    datetime.date(2026, 2, 7), # Saturday
    datetime.date(2026, 2, 8)  # Sunday
]

class WorkerCollector:
    def __init__(self):
        print("[WORKER] Initializing...")
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        try:
            self.jv = win32com.client.Dispatch("JVDTLab.JVLink")
            res = self.jv.JVInit("UNKNOWN")
            if res != 0:
                print(f"[ERROR] JVInit Failed: {res}")
                sys.exit(1)
            print("[WORKER] JV-Link Connected.")
        except Exception as e:
            print(f"[ERROR] JV-Link Exception: {e}")
            sys.exit(1)

    def run(self):
        for target_date in TARGET_DATES:
            self.fetch_data("0B15", target_date) # 0B15: Race Card (Syussouba)
            
        self.jv.JVClose()
        print("[WORKER] All Tasks Completed.")

    def fetch_data(self, dataspec, target_date):
        date_str = target_date.strftime("%Y%m%d")
        print(f"\n>> Processing {date_str} (Spec: {dataspec})...")
        
        # Option 2: Read from Local Cache (TARGET download data)
        # Assuming user has downloaded data via TARGET.
        # JVOpen(dataspec, key, option, read_count, download_count, last_key)
        res = self.jv.JVOpen(dataspec, f"{date_str}000000", 2, 0, 0, "")
        
        if res != 0:
            print(f"[WARN] JVOpen Failed (Code {res}). User might need to download data in TARGET.")
            return

        count = 0
        uploaded = 0
        
        while True:
            try:
                # JVRead(buff, size, filename)
                # In Python win32com, it usually returns (ret_code, buff_str, filename_str)
                # buffer size 200KB is enough for one record
                read_res = self.jv.JVRead("", 200000, "")
                
                # Handle Tuple Return
                if isinstance(read_res, tuple):
                    ret_code = read_res[0]
                    raw_data = read_res[1]
                else:
                    ret_code = read_res
                    raw_data = ""

                if ret_code == 0: break # END
                if ret_code == -1: break # EOF
                
                if ret_code > 0:
                    count += 1
                    # Basic Parsing for ID (First 10-15 chars usually contain Date/Race)
                    # For 0B15, YYYYMMDD is usually at the start or standard location.
                    # We'll use a generated ID for Supabase uniqueness.
                    row_id = f"{dataspec}_{date_str}_{count}"
                    
                    payload = {
                        "race_id": row_id,
                        "data_type": dataspec,
                        "content": {
                            "date": date_str,
                            "raw_string": str(raw_data).strip()
                        },
                        "status": "pending",
                        "timestamp": str(datetime.datetime.now())
                    }
                    
                    # Upload
                    self.supabase.table("raw_race_data").insert(payload).execute()
                    uploaded += 1
                    print(f"   Uploaded {uploaded} records...", end="\r")

            except Exception as e:
                print(f"\n[ERROR] Read Loop: {e}")
                break
        
        print(f"\n   Total {uploaded} records uploaded for {date_str}.")
        self.jv.JVClose() # Close this handle (Not JVLink itself? JVClose closes the open session)

if __name__ == "__main__":
    worker = WorkerCollector()
    worker.run()
