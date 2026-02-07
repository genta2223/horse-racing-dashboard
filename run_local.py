"""
JRA Automated Betting System - Local Runner
============================================
This script runs the complete betting pipeline on your local Windows PC.

Features:
- JV-Link data collection (requires TARGETでダウンロード済みのデータ)
- AI prediction (V4.1 Hybrid Strategy)
- IPAT automated purchasing

Usage:
    python run_local.py

Requirements:
    - Windows PC with JV-Link installed
    - Chrome browser installed
    - .env file with credentials configured
"""

import os
import sys
import time
import datetime
import threading
import schedule
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import workers
try:
    from worker_collector import WorkerCollector
    JV_LINK_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] JV-Link not available: {e}")
    JV_LINK_AVAILABLE = False

from worker_predictor_v4_1 import PredictorV4_1, run_prediction_cycle
from worker_shopper import Shopper
from cloud_manager import CloudManager
from supabase import create_client

# --- Configuration ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Betting Schedule (JST)
RACE_START_HOUR = 10  # First race around 10:00
RACE_END_HOUR = 16    # Last race around 16:30
CYCLE_INTERVAL_MINUTES = 5  # Check every 5 minutes during race hours

class LocalRunner:
    def __init__(self):
        print("=" * 50)
        print("JRA Automated Betting System - Local Mode")
        print("=" * 50)
        
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.cm = CloudManager(self.supabase)
        self.shopper = Shopper(self.supabase)
        self.running = True
        
        # Log startup
        self.cm.log_system_event("INFO", "Local Runner Started", 
            f"JV-Link: {'Available' if JV_LINK_AVAILABLE else 'Not Available'}")
    
    def collect_data(self):
        """Collect data from JV-Link (if available)"""
        if not JV_LINK_AVAILABLE:
            print("[SKIP] JV-Link not available. Using cached data.")
            return False
        
        try:
            print("\n[DATA] Starting JV-Link data collection...")
            collector = WorkerCollector()
            collector.run()
            self.cm.log_system_event("INFO", "Data Collection Complete", "JV-Link data uploaded")
            return True
        except Exception as e:
            print(f"[ERROR] Data collection failed: {e}")
            self.cm.log_system_event("ERROR", "Data Collection Failed", str(e))
            return False
    
    def run_prediction(self):
        """Run AI prediction cycle"""
        try:
            print("\n[AI] Running prediction cycle...")
            run_prediction_cycle()
            self.cm.log_system_event("INFO", "Prediction Complete", "Bets queued")
            return True
        except Exception as e:
            print(f"[ERROR] Prediction failed: {e}")
            self.cm.log_system_event("ERROR", "Prediction Failed", str(e))
            return False
    
    def run_shopper(self):
        """Execute approved bets via IPAT"""
        try:
            # Check if auto-bet is enabled
            if not self.cm.is_auto_bet_active():
                print("[SKIP] Auto-bet is DISABLED in dashboard.")
                return False
            
            print("\n[BUY] Running shopper cycle...")
            daily_cap = self.cm.get_daily_cap()
            self.shopper.check_and_buy(daily_limit_override=daily_cap)
            return True
        except Exception as e:
            print(f"[ERROR] Shopper failed: {e}")
            self.cm.log_system_event("CRITICAL", "Shopper Failed", str(e))
            self.shopper.send_error_alert(e, context="Local Shopper")
            return False
    
    def is_race_hours(self):
        """Check if current time is within race hours"""
        now = datetime.datetime.now()
        return RACE_START_HOUR <= now.hour < RACE_END_HOUR
    
    def is_race_day(self):
        """Check if today is a race day (Sat/Sun or special weekday)"""
        today = datetime.date.today()
        # Saturday = 5, Sunday = 6
        return today.weekday() in [5, 6]
    
    def run_cycle(self):
        """Single betting cycle"""
        print(f"\n{'='*50}")
        print(f"[CYCLE] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        # Skip if not race day/hours
        if not self.is_race_day():
            print("[INFO] Not a race day (Sat/Sun). Skipping cycle.")
            return
        
        if not self.is_race_hours():
            print(f"[INFO] Outside race hours ({RACE_START_HOUR}:00-{RACE_END_HOUR}:00). Skipping.")
            return
        
        # Full cycle
        self.run_prediction()
        self.run_shopper()
    
    def run_morning_data_collection(self):
        """Morning data collection at 9:00 AM"""
        print("\n[MORNING] Starting data collection...")
        if self.is_race_day():
            self.collect_data()
        else:
            print("[SKIP] Not a race day.")
    
    def start(self):
        """Start the local runner with scheduler"""
        print("\n[SCHEDULER] Setting up schedule...")
        
        # Morning data collection at 9:00 AM on race days
        schedule.every().saturday.at("09:00").do(self.run_morning_data_collection)
        schedule.every().sunday.at("09:00").do(self.run_morning_data_collection)
        
        # Betting cycles every 5 minutes during race hours
        schedule.every(CYCLE_INTERVAL_MINUTES).minutes.do(self.run_cycle)
        
        print(f"[SCHEDULER] Data collection: Sat/Sun 09:00")
        print(f"[SCHEDULER] Betting cycles: Every {CYCLE_INTERVAL_MINUTES} min during {RACE_START_HOUR}:00-{RACE_END_HOUR}:00")
        print("\n[READY] System is now running. Press Ctrl+C to stop.\n")
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(30)  # Check schedule every 30 seconds
        except KeyboardInterrupt:
            print("\n[STOP] Shutting down...")
            self.cm.log_system_event("INFO", "Local Runner Stopped", "Manual shutdown")
            if self.shopper.driver:
                self.shopper.driver.quit()
            print("[DONE] Goodbye!")

def main():
    # Quick environment check
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "IPAT_INET_ID", "IPAT_SUBSCRIBER_ID"]
    missing = [v for v in required_vars if not os.getenv(v)]
    
    if missing:
        print(f"[ERROR] Missing environment variables: {missing}")
        print("Please check your .env file.")
        sys.exit(1)
    
    runner = LocalRunner()
    
    # Option: Run once immediately for testing
    if "--once" in sys.argv:
        print("[TEST MODE] Running single cycle...")
        runner.run_cycle()
    else:
        runner.start()

if __name__ == "__main__":
    main()
