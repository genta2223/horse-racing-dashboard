#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Supabase Data Uploader (Step 2)
Uploads local JV-Link data files to Supabase
"""

import os
import sys
import json
import datetime
import argparse
import urllib.request
import urllib.error
from dotenv import load_dotenv

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Input directory for downloaded data
INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jv_data")


def upload_to_supabase(payload: dict) -> bool:
    """Upload a single record to Supabase via direct HTTP"""
    try:
        # Serialize to JSON with ensure_ascii=True
        json_data = json.dumps(payload, ensure_ascii=True)
        json_bytes = json_data.encode('ascii')
        
        url = f"{SUPABASE_URL}/rest/v1/raw_race_data"
        
        req = urllib.request.Request(
            url,
            data=json_bytes,
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Prefer": "resolution=merge-duplicates"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201)
            
    except urllib.error.HTTPError as he:
        err_body = he.read().decode('utf-8', errors='replace')[:200]
        print(f"\n[ERROR] HTTP {he.code}: {err_body}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Upload failed: {e}")
        return False


def parse_race_id(raw_data: str) -> str:
    """Extract race_id from JV-Link record (ASCII only)"""
    try:
        if len(raw_data) < 20:
            return None
        # Extract characters 2-18, filter to ASCII only
        race_id_raw = raw_data[2:18]
        return ''.join(c for c in race_id_raw if ord(c) < 128)
    except:
        return None


def upload_file(file_path: str, dataspec: str, date_str: str) -> int:
    """Upload a single data file to Supabase"""
    print(f"\n>> Uploading {os.path.basename(file_path)}...")
    
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return 0
    
    uploaded = 0
    count = 0
    
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            count += 1
            
            # Parse race_id
            race_id = parse_race_id(line)
            if not race_id:
                race_id = f"{dataspec}_{date_str}_{count:06d}"
            
            # Convert raw data to Base64 for safe storage
            import base64
            try:
                raw_bytes = line.encode('utf-8', errors='replace')
                raw_b64 = base64.b64encode(raw_bytes[:2000]).decode('ascii')
            except:
                raw_b64 = "[encoding error]"
            
            # Prepare payload
            payload = {
                "race_id": race_id,
                "data_type": dataspec,
                "race_date": date_str,
                "content": json.dumps({"record_type": line[:2] if len(line) >= 2 else "XX"}, ensure_ascii=True),
                "raw_string": raw_b64,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": "pending"
            }
            
            if upload_to_supabase(payload):
                uploaded += 1
                print(f"   Uploaded {uploaded}/{count}...", end="\r")
    
    print(f"\n   >> {uploaded}/{count} records uploaded")
    return uploaded


def main():
    print("=" * 50)
    print("Supabase Data Uploader")
    print("=" * 50)
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)
    
    print(f"[OK] Supabase URL: {SUPABASE_URL[:30]}...")
    
    parser = argparse.ArgumentParser(description="Upload JV-Link data to Supabase")
    parser.add_argument("--date", type=str, help="Target date YYYYMMDD (default: today)")
    parser.add_argument("--spec", type=str, default="0B15", help="Data spec (default: 0B15)")
    args = parser.parse_args()
    
    # Determine target date
    if args.date:
        date_str = args.date
    else:
        date_str = datetime.date.today().strftime("%Y%m%d")
    
    print(f"[TARGET] Date: {date_str}, Spec: {args.spec}")
    
    # Find the data file
    file_path = os.path.join(INPUT_DIR, f"{args.spec}_{date_str}.txt")
    
    if not os.path.exists(file_path):
        print(f"[ERROR] Data file not found: {file_path}")
        print("Please run step1_download.py first.")
        sys.exit(1)
    
    # Upload
    total = upload_file(file_path, args.spec, date_str)
    
    print(f"\n{'='*50}")
    print(f"[DONE] Total {total} records uploaded to Supabase.")


if __name__ == "__main__":
    main()
