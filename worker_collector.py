"""
JRA Data Collector (Local PC - Windows Only)
=============================================
Fetches race data via JV-Link and uploads to Supabase.

Requirements:
    - Windows PC with JV-Link SDK installed
    - TARGETでダウンロード済みのデータ
    - .env file with SUPABASE_URL and SUPABASE_KEY

Usage:
    python worker_collector.py              # Collect today's data
    python worker_collector.py --date 20260207  # Specific date

For Windows Task Scheduler:
    Program: python
    Arguments: C:\\TFJV\\my-racing-dashboard\\worker_collector.py
    Start in: C:\\TFJV\\my-racing-dashboard
"""

import os
import sys
import json
import datetime
import argparse
import urllib.request
import urllib.error
from dotenv import load_dotenv
from jra_parser import JRAParser

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Check for Windows
if sys.platform != "win32":
    print("[ERROR] This script requires Windows (JV-Link uses COM).")
    sys.exit(1)

import win32com.client
# Note: Using direct HTTP instead of supabase client for encoding control

class DataUploader:
    """Collects JRA data via JV-Link and uploads to Supabase"""
    
    def __init__(self):
        print("=" * 50)
        print("JRA Data Collector - Local Uploader")
        print("=" * 50)
        
        # Store Supabase credentials for direct HTTP calls
        self.supabase_url = SUPABASE_URL
        self.supabase_key = SUPABASE_KEY
        
        # Initialize JV-Link
        try:
            self.jv = win32com.client.Dispatch("JVDTLab.JVLink")
            # JRA-VAN Data Lab Software ID
            # Use UNKNOWN for local cache access (option 4)
            res = self.jv.JVInit("UNKNOWN")
            if res != 0:
                print(f"[ERROR] JVInit Failed: {res}")
                sys.exit(1)
            print("[OK] JV-Link Connected.")
        except Exception as e:
            print(f"[ERROR] JV-Link Exception: {e}")
            print("Make sure JV-Link SDK is installed and registered.")
            sys.exit(1)
    
    def parse_race_id(self, raw_data: str) -> str:
        """Extract race_id from raw string using JRAParser (Byte aligned)"""
        try:
            parser = JRAParser(raw_data)
            return parser.parse("0B15").get("race_id") # Any spec works for ID position
        except:
            return None
    
    def parse_odds_data(self, raw_data: str, dataspec: str) -> dict:
        """Parse JV-Link record using robust JRAParser"""
        try:
            parser = JRAParser(raw_data)
            parsed = parser.parse(dataspec)
            if parsed:
                return parsed
            return {"raw": raw_data[:100], "parse_error": "JRAParser returned None"}
        except Exception as e:
            return {"raw": raw_data[:100], "parse_error": str(e)}
    
    def fetch_and_upload(self, dataspec: str, target_date: datetime.date):
        """Fetch data from JV-Link and upload to Supabase"""
        date_str = target_date.strftime("%Y%m%d")
        print(f"\n>> Fetching {dataspec} for {date_str}...")
        
        # Data types:
        # 速報系 (Real-time): 0B15, 0B31, 0B32 etc. -> Use JVRTOpen
        # 蓄積系 (Historical): RACE, BLOD etc. -> Use JVOpen
        
        # 0B15, 0B31, 0B32 are 速報系 (real-time) data
        # Must use JVRTOpen instead of JVOpen!
        
        # JVRTOpen signature: JVRTOpen(dataspec, key)
        # key = YYYYMMDD for date-based real-time data
        open_res = self.jv.JVRTOpen(dataspec, date_str)
        
        # Handle tuple result (retcode, readcount)
        if isinstance(open_res, tuple):
            ret_code = open_res[0]
            read_count = open_res[1] if len(open_res) > 1 else 0
        else:
            ret_code = open_res
            read_count = 0
        
        print(f"   JVRTOpen result: code={ret_code}, read={read_count}")
        
        if ret_code < 0:
            print(f"[WARN] JVRTOpen failed (Code {ret_code}).")
            if ret_code == -1:
                print("   -> Invalid dataspec")
            elif ret_code == -2:
                print("   -> Data not available")
            elif ret_code == -111:
                print("   -> Server authentication failed. Check subscription.")
            elif ret_code == -202:
                print("   -> Previous JVRTOpen not closed. Calling JVClose...")
                self.jv.JVClose()
            return 0
        
        # Note: read_count from COM may not be reliable in Python
        # Always try JVRead and let it determine when data ends
        print(f"   Session opened. Attempting to read data...")
        
        count = 0
        uploaded = 0
        
        while True:
            try:
                # JVRead returns (ret_code, buffer, filename)
                read_res = self.jv.JVRead("", 200000, "")
                
                if isinstance(read_res, tuple):
                    ret_code = read_res[0]
                    raw_data = str(read_res[1]).strip() if read_res[1] else ""
                else:
                    ret_code = read_res
                    raw_data = ""
                
                # End conditions
                if ret_code == 0:  # No more data
                    break
                if ret_code == -1:  # EOF
                    break
                if ret_code < 0:  # Error
                    print(f"[WARN] JVRead error: {ret_code}")
                    break
                
                if ret_code > 0 and raw_data:
                    count += 1
                    
                    # Parse ID
                    safe_race_id = self.parse_race_id(raw_data)
                    if not safe_race_id:
                        continue
                    
                    # Parse odds/card data
                    parsed_data = self.parse_odds_data(raw_data, dataspec)
                    
                    # Encode raw_data as Base64 to avoid encoding issues
                    import base64
                    try:
                        if isinstance(raw_data, bytes):
                            raw_bytes = raw_data
                        else:
                            raw_bytes = str(raw_data).encode('utf-8', errors='replace')
                        # Store as Base64 string (ASCII-safe)
                        safe_raw = base64.b64encode(raw_bytes[:2000]).decode('ascii')
                    except Exception as enc_err:
                        safe_raw = f"[encoding error: {enc_err}]"
                    
                    if not safe_race_id:
                        safe_race_id = f"UNKNOWN_{count:06d}"
                    
                    # Prepare payload for Supabase - all ASCII-safe now
                    payload = {
                        "race_id": safe_race_id,
                        "data_type": dataspec,
                        "race_date": date_str,
                        "content": json.dumps(parsed_data, ensure_ascii=False),
                        "raw_string": safe_raw,  # Base64 encoded
                    }
                    
                    # DEBUG: Verify all fields are ASCII
                    for key, val in payload.items():
                        try:
                            str(val).encode('ascii')
                        except UnicodeEncodeError as ue:
                            print(f"\n[DEBUG] Field '{key}' has non-ASCII: {ue}")
                            print(f"[DEBUG] Value preview: {repr(str(val)[:50])}")
                    
                    # Use direct HTTP to Supabase REST API (bypass client encoding issues)
                    try:
                        # Serialize to JSON with ensure_ascii=True
                        json_data = json.dumps(payload, ensure_ascii=True)
                        json_bytes = json_data.encode('ascii')
                        
                        # Supabase REST API endpoint for upsert
                        url = f"{self.supabase_url}/rest/v1/raw_race_data"
                        
                        req = urllib.request.Request(
                            url,
                            data=json_bytes,
                            headers={
                                "Content-Type": "application/json",
                                "apikey": self.supabase_key,
                                "Authorization": f"Bearer {self.supabase_key}",
                                "Prefer": "resolution=merge-duplicates"  # upsert
                            },
                            method="POST"
                        )
                        
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            if resp.status in (200, 201):
                                uploaded += 1
                                print(f"   Uploaded {uploaded} records...", end="\r")
                            else:
                                print(f"\n[WARN] HTTP {resp.status}")
                                
                    except urllib.error.HTTPError as he:
                        err_body = he.read().decode('utf-8', errors='replace')[:200]
                        print(f"\n[ERROR] HTTP {he.code}: {err_body}")
                    except Exception as e:
                        print(f"\n[ERROR] Upload failed: {e}")
                        
            except Exception as e:
                print(f"\n[ERROR] Read loop: {e}")
                break
        
        # Close this data session
        self.jv.JVClose()
        print(f"\n   >> {dataspec}: {uploaded}/{count} records uploaded.")
        return uploaded
    
    def fetch_odds_by_race(self, dataspec: str, race_key: str, date_str: str):
        """Fetch odds data for a specific race using race-level key"""
        # 0B31/0B32 require race-level key: YYYYMMDDJJKKHHRR or YYYYMMDDJJRR
        # race_key format from 0B15: YYYYMMDDJJKKHHRR (16 chars)
        
        open_res = self.jv.JVRTOpen(dataspec, race_key)
        
        if isinstance(open_res, tuple):
            ret_code = open_res[0]
        else:
            ret_code = open_res
        
        if ret_code < 0:
            # Silently skip - odds may not be available yet for this race
            self.jv.JVClose()
            return 0
        
        uploaded = 0
        while True:
            try:
                read_res = self.jv.JVRead("", 200000, "")
                
                if isinstance(read_res, tuple):
                    ret_code = read_res[0]
                    raw_data = str(read_res[1]).strip() if read_res[1] else ""
                    
                    # Correct Dataspec detection from filename
                    # JVRead returns (ret_code, data, size, filename)
                    if len(read_res) >= 4:
                         filename = read_res[3]
                         if filename and len(filename) >= 4:
                             real_dataspec = filename[:4]
                         else:
                             real_dataspec = dataspec
                    else:
                         real_dataspec = dataspec
                else:
                    ret_code = read_res
                    raw_data = ""
                    real_dataspec = dataspec
                
                if ret_code == 0 or ret_code == -1 or ret_code < 0:
                    break
                
                if ret_code > 0 and raw_data:
                    # Parse odds data using REAL spec
                    parsed_data = self.parse_odds_data(raw_data, real_dataspec)
                    
                    import base64
                    try:
                        if isinstance(raw_data, bytes):
                            raw_bytes = raw_data
                        else:
                            raw_bytes = str(raw_data).encode('utf-8', errors='replace')
                        safe_raw = base64.b64encode(raw_bytes[:2000]).decode('ascii')
                    except Exception:
                        safe_raw = "[encoding error]"
                    
                    payload = {
                        "race_id": race_key[:16],  # Use full race key as ID
                        "data_type": real_dataspec, # Use Correct Data Type
                        "race_date": date_str,
                        "content": json.dumps(parsed_data, ensure_ascii=False),
                        "raw_string": safe_raw,
                    }
                    
                    try:
                        json_data = json.dumps(payload, ensure_ascii=True)
                        json_bytes = json_data.encode('ascii')
                        
                        url = f"{self.supabase_url}/rest/v1/raw_race_data"
                        
                        req = urllib.request.Request(
                            url,
                            data=json_bytes,
                            headers={
                                "Content-Type": "application/json",
                                "apikey": self.supabase_key,
                                "Authorization": f"Bearer {self.supabase_key}",
                                "Prefer": "resolution=merge-duplicates"
                            },
                            method="POST"
                        )
                        
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            if resp.status in (200, 201):
                                uploaded += 1
                                
                    except Exception:
                        pass
                        
            except Exception:
                break
        
        self.jv.JVClose()
        return uploaded

    def fetch_race_results(self, start_date: datetime.date, end_date: datetime.date):
        """Fetch 0B12 (Race Results) using JVRTOpen (Realtime/Diff) for specific range"""
        print(f"\n>> Fetching 0B12 (Race Results) from {start_date} to {end_date}...")
        
        total = 0
        current = start_date
        while current <= end_date:
            # JRA-VAN 0B12 is available via JVRTOpen with YYYYMMDD key
            # It returns the latest results (Preliminary or Fixed)
            uploaded = self.fetch_and_upload("0B12", current)
            total += uploaded
            current += datetime.timedelta(days=1)
            
        print(f"\n   >> 0B12 Total: {total} records uploaded.")
        return total

    def run(self, target_date: datetime.date = None, mode: str = "auto"):
        """Main execution with mode support"""
        if target_date is None:
            target_date = datetime.date.today()
        
        date_str = target_date.strftime("%Y%m%d")
        print(f"\n[TARGET DATE] {target_date} [MODE] {mode}")
        
        total_uploaded = 0
        
        # MODE: RESULTS (Past 0B12)
        if mode in ["results", "friday"]:
            # Fetch past 7 days results
            start_date = target_date - datetime.timedelta(days=7)
            end_date = target_date 
            print(f"\n>> Phase: Results (0B12) from {start_date} to {end_date}")
            total_uploaded += self.fetch_race_results(start_date, end_date)
            
        # MODE: CARDS (Upcoming 0B15)
        if mode in ["cards", "friday", "auto"]:
            print(f"\n>> Phase: Race Cards (0B15) for {date_str}...")
            total_uploaded += self.fetch_and_upload("0B15", target_date)
            
        # MODE: ODDS (Realtime 0B31/32)
        if mode in ["odds", "auto"]:
            # Only run if we have race keys (which implies we fetched Cards or queried DB)
            # Query DB for keys
            race_keys = set()
            try:
                url = f"{self.supabase_url}/rest/v1/raw_race_data"
                req = urllib.request.Request(
                    f"{url}?select=race_id&data_type=eq.0B15&race_date=eq.{date_str}",
                    headers={"apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}"},
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    for row in data:
                        rid = row.get('race_id', '')
                        if rid and len(rid) >= 16: race_keys.add(rid[:16])
            except: pass
            
            if race_keys:
                print(f"\n>> Phase: Realtime Odds (0B31/0B32) for {len(race_keys)} races...")
                for dataspec in ["0B31", "0B32"]:
                    spec_uploaded = 0
                    for race_key in sorted(race_keys):
                        spec_uploaded += self.fetch_odds_by_race(dataspec, race_key, date_str)
                    print(f"   >> {dataspec}: {spec_uploaded} uploaded.")
                    total_uploaded += spec_uploaded
        
        print(f"\n[DONE] Total {total_uploaded} records.")
        return total_uploaded


def main():
    parser = argparse.ArgumentParser(description="JRA Data Collector")
    parser.add_argument("--date", type=str, help="Target date (YYYYMMDD)")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "results", "cards", "odds", "friday"], help="Collection mode")
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y%m%d").date()
        except ValueError:
            print(f"[ERROR] Invalid date format: {args.date}")
            sys.exit(1)
            
    uploader = DataUploader()
    uploader.run(target_date, args.mode)



if __name__ == "__main__":
    main()
