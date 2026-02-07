#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JV-Link Data Downloader (Step 1)
Downloads JRA race data to local files only - no Supabase upload
"""

import os
import sys
import datetime
import argparse

# Check for Windows
if sys.platform != "win32":
    print("[ERROR] This script requires Windows (JV-Link uses COM).")
    sys.exit(1)

import win32com.client

# Output directory for downloaded data
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jv_data")

class JVDownloader:
    """Downloads JRA data via JV-Link to local files"""
    
    def __init__(self):
        print("=" * 50)
        print("JV-Link Data Downloader")
        print("=" * 50)
        
        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"[OK] Output directory: {OUTPUT_DIR}")
        
        # Initialize JV-Link
        try:
            self.jv = win32com.client.Dispatch("JVDTLab.JVLink")
            res = self.jv.JVInit("UNKNOWN")
            if res != 0:
                print(f"[ERROR] JVInit Failed: {res}")
                sys.exit(1)
            print("[OK] JV-Link Connected.")
        except Exception as e:
            print(f"[ERROR] JV-Link Exception: {e}")
            sys.exit(1)
    
    def download_data(self, dataspec: str, target_date: datetime.date) -> int:
        """Download data for a specific dataspec and date"""
        date_str = target_date.strftime("%Y%m%d")
        
        print(f"\n>> Downloading {dataspec} for {date_str}...")
        
        # Open real-time data session
        open_res = self.jv.JVRTOpen(dataspec, date_str)
        
        if isinstance(open_res, tuple):
            ret_code = open_res[0]
            read_count = open_res[1] if len(open_res) > 1 else 0
        else:
            ret_code = open_res
            read_count = 0
        
        print(f"   JVRTOpen result: code={ret_code}, read={read_count}")
        
        if ret_code < 0:
            print(f"[ERROR] JVRTOpen failed: {ret_code}")
            if ret_code == -202:
                self.jv.JVClose()
            return 0
        
        # Output file path
        output_file = os.path.join(OUTPUT_DIR, f"{dataspec}_{date_str}.txt")
        
        count = 0
        
        # Open file for writing with UTF-8 encoding
        with open(output_file, "w", encoding="utf-8", errors="replace") as f:
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
                        # Write record to file
                        f.write(raw_data + "\n")
                        print(f"   Downloaded {count} records...", end="\r")
                        
                except Exception as e:
                    print(f"\n[ERROR] Read loop: {e}")
                    break
        
        # Close data session
        self.jv.JVClose()
        
        print(f"\n   >> {dataspec}: {count} records saved to {output_file}")
        return count
    
    def run(self, target_date: datetime.date = None):
        """Main execution"""
        if target_date is None:
            target_date = datetime.date.today()
        
        print(f"\n[TARGET DATE] {target_date}")
        
        # Data types to download
        specs = [
            ("0B15", "Race Card (速報レース情報)"),
        ]
        
        total = 0
        for spec, name in specs:
            count = self.download_data(spec, target_date)
            total += count
        
        print(f"\n{'='*50}")
        print(f"[DONE] Total {total} records downloaded.")
        print(f"Files saved to: {OUTPUT_DIR}")
        return total


def main():
    parser = argparse.ArgumentParser(description="Download JRA data from JV-Link")
    parser.add_argument("--date", type=str, help="Target date YYYYMMDD (default: today)")
    parser.add_argument("--spec", type=str, default="0B15", 
                        help="Data spec: 0B15=Race Card, 0B12=Results (default: 0B15)")
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y%m%d").date()
        except:
            print(f"[ERROR] Invalid date format: {args.date}")
            sys.exit(1)
    
    downloader = JVDownloader()
    
    # Use specified dataspec
    if target_date is None:
        target_date = datetime.date.today()
    
    print(f"\n[TARGET DATE] {target_date}")
    count = downloader.download_data(args.spec, target_date)
    
    print(f"\n{'='*50}")
    print(f"[DONE] Total {count} records downloaded.")


if __name__ == "__main__":
    main()
