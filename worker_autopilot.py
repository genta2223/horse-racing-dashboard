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
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")
    except UnicodeEncodeError:
        safe_msg = message.encode('cp932', errors='replace').decode('cp932')
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {safe_msg}")

def run_script(cmd, script_name, args=None):
    if args is None: args = []
    try:
        full_cmd = cmd + [script_name] + args
        log(f"Starting {script_name} with {full_cmd}...")
        result = subprocess.run(
            full_cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            cwd=r"C:\TFJV\my-racing-dashboard"
        )
        
        if result.returncode == 0:
            log(f"[OK] {script_name} completed successfully.")
            # Show last 5 lines of output
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    try:
                        print(f"    > {line}")
                    except:
                        pass
        else:
            log(f"[ERROR] {script_name} failed:")
            if result.stderr:
                try:
                    print(result.stderr[:500])
                except:
                    pass
    except Exception as e:
        log(f"[ERROR] Error running {script_name}: {e}")

def main():
    log("=" * 60)
    log("AI Auto-Pilot Started (Hybrid Mode: 32bit/64bit)")
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

        if now < start_time:
            wait_seconds = (start_time - now).total_seconds()
            log(f"Sleeping until 9:00 AM... ({wait_seconds/60:.0f} minutes)")
            time.sleep(min(1800, wait_seconds))
            continue
        elif now > end_time:
            log("Racing finished for today. Exiting.")
            break

        # === Execute Cycle ===
        cycle_count += 1
        log(f"--- Cycle #{cycle_count} ---")

        # 1. Data Collection (32bit Python for JRA-VAN)
        run_script(CMD_COLLECT, "worker_collector.py", args=["--date", today_str])

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
