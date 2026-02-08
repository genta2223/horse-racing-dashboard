"""
worker_autopilot.py
===================
Hybrid Mode Auto-Pilot:
- Data Collection (JRA-VAN): 32bit Python (required by JVLink SDK)
- AI Prediction (Pandas/Scikit-learn): 64bit Python (modern standard)

Usage: py worker_autopilot.py
"""

import time
import subprocess
import datetime
import sys
import os

# Change to the script directory
os.chdir(r"C:\TFJV\my-racing-dashboard")

# === Environment Configuration ===
# Collection: 32bit Python (JRA-VAN requires 32bit)
CMD_COLLECT = ["py", "-3.11-32"] 

# Prediction: 64bit Python (default, better for ML libraries)
CMD_PREDICT = ["py"] 

def log(message):
    # Windows cp932 safe output
    try:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)
    except UnicodeEncodeError:
        safe_msg = message.encode('cp932', errors='replace').decode('cp932')
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {safe_msg}", flush=True)

def run_script(cmd, script_name, args=None):
    if args is None: args = []
    try:
        full_cmd = cmd + [script_name] + args
        log(f"Starting {script_name} with {full_cmd}...")
        
        # Run subprocess and stream output directly
        result = subprocess.run(
            full_cmd, 
            capture_output=False,  # Stream to stdout
            text=True, 
            encoding='utf-8',
            errors='replace',
            cwd=r"C:\TFJV\my-racing-dashboard"
        )
        
        if result.returncode == 0:
            log(f"[OK] {script_name} completed successfully.")
        else:
            log(f"[ERROR] {script_name} failed with code {result.returncode}")

    except Exception as e:
        log(f"[ERROR] Error running {script_name}: {e}")

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-friday", action="store_true", help="Force run Friday sequence")
    args = parser.parse_args()

    log("=" * 60)
    log("AI Auto-Pilot Started (Hybrid Mode: 32bit/64bit)")
    if args.force_friday:
        log("MODE: Force Friday Sequence")
    log("=" * 60)
    log("Data Collection: 32bit Python (JRA-VAN)")
    log("AI Prediction:   64bit Python (Pandas/Sklearn)")
    log("Running from 09:00 to 16:30")
    log("=" * 60)

    cycle_count = 0
    
    while True:
        now = datetime.datetime.now()
        today_str = now.strftime("%Y%m%d")
        
        # Operating hours: 9:00 AM to 4:30 PM
        start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=16, minute=30, second=0, microsecond=0)

        # Force run bypasses time check
        if not args.force_friday:
            if now < start_time:
                wait_seconds = (start_time - now).total_seconds()
                log(f"Sleeping until 9:00 AM... ({wait_seconds/60:.0f} minutes)")
                time.sleep(min(1800, wait_seconds))
                continue
            elif now > end_time:
                log("Racing finished for today. Exiting.")
                break

        # === Friday Golden Sequence ===
        # Check if it's Friday and time is after 18:00 (for weekend prep)
        # OR manual override via command line (TODO)
        # For now, let's implement a specific trigger or check day of week
        weekday = now.weekday() # Monday=0, Friday=4
        if args.force_friday or (weekday == 4 and now.hour >= 18):
            log("--- FRIDAY GOLDEN SEQUENCE ---")
            log("Phase 1: Fetch Past Results (0B12)")
            run_script(CMD_COLLECT, "worker_collector.py", args=["--mode", "results"])
            
            log("Phase 2: Fetch Weekend Cards (0B15)")
            run_script(CMD_COLLECT, "worker_collector.py", args=["--mode", "cards", "--date", today_str])
            
            log("Phase 3: AI Prediction")
            run_script(CMD_PREDICT, "worker_predict.py", args=["--date", today_str])
            
            log("Friday Sequence Completed. Exiting to wait for weekend.")
            break

        # === Execute Regular Cycle ===
        cycle_count += 1
        log(f"--- Cycle #{cycle_count} ---")

        # 1. Data Collection (32bit Python for JRA-VAN)
        run_script(CMD_COLLECT, "worker_collector.py", args=["--mode", "auto", "--date", today_str])

        # 2. AI Prediction (64bit Python for ML libraries)
        run_script(CMD_PREDICT, "worker_predict.py", args=["--date", today_str])

        log("Waiting 10 minutes for next update...")
        log("-" * 40)
        time.sleep(600)  # 10 minutes

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
        sys.exit(0)
