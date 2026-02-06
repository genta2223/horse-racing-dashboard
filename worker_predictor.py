import os
import sys
import time
import json
import subprocess
import datetime
import smtplib
from email.mime.text import MIMEText
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv

# Try importing Brain (Simulated if missing in dev env)
try:
    from local_engine.brain import Brain
    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False
    print("[WARN] Brain module missing. Running in Logic-Only Check Mode.")

# --- Config ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MAIL_SENDER = os.getenv("MAIL_SENDER")
MAIL_APP_PASS = os.getenv("MAIL_APP_PASS")
MAIL_RECEIVER = os.getenv("MAIL_RECEIVER")
EV_THRESHOLD = 1.34

# --- JV Parser (Hypothetical Offsets - User Verification Required) ---
class JVParser:
    """
    Parses fixed-width JV-Data strings.
    offsets should be verified against JRA-VAN SDK spec.
    """
    @staticmethod
    def parse_0B15(raw_str):
        """ Syussouba (Race Card) """
        # TODO: Adjust offsets based on real data
        try:
            # Example Structure:
            # Date(8), Place(2), Race(2)... HorseNum(2) at pos X... HorseName(36) at pos Y
            # This is a PLACEHOLDER implementation.
            # We assume raw_str is CSV or fixed width.
            # If win32com returns CSV-like string, split by ','.
            # If fixed width, use slice.
            # JRA-VAN JVRead usually returns Fixed Width encoded in Shift-JIS (decoded here).
             
            # Attempting to parse as if it were a standard record
            # We'll use a safer approach: Look for patterns or assume CSV for now if using DataLab CSV method
            # BUT worker_collector uses JVRead which returns Fixed Width.
            
            # MOCK IMPLEMENTATION for parsing
            # We will return a dict with mock data if raw_str is "MOCK"
            # Otherwise we try slicing.
            
            # Since we don't have the spec, and the user prioritized "Check Logic",
            # We will implement the Logic check assuming we HAVE parsed data.
            # IN PRODUCTION: The User MUST replace this method with the actual Parser.
            
            data = {
                'race_id': raw_str[0:12] if len(raw_str) > 12 else "Unknown",
                'horse_num': int(raw_str[20:22]) if len(raw_str) > 22 and raw_str[20:22].isdigit() else 0,
                'horse_name': raw_str[30:50].strip() if len(raw_str) > 50 else "Unknown",
                'features': {
                   'prev_3f': 34.5 # Dummy
                }
            }
            return data
        except Exception:
            return None

    @staticmethod
    def parse_0B31(raw_str):
        """ Odds (Tan/Fuku) """
        try:
            # Same placeholder logic
            return {
                'race_id': raw_str[0:12] if len(raw_str) > 12 else "Unknown",
                'odds': {
                    1: 2.5, # Dummy Map: HorseNum -> Odds
                    # In reality, parse the repeated fields
                }
            }
        except:
            return None

class Predictor:
    def __init__(self):
        print("[PREDICTOR] Initializing...")
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        if BRAIN_AVAILABLE:
            self.brain = Brain(model_path="local_engine/final_model.pkl")
        else:
            self.brain = None
            
        self.history_df = None # Load history here if needed

    def send_alert(self, subject, body):
        if not all([MAIL_SENDER, MAIL_APP_PASS, MAIL_RECEIVER]):
            print(f"[ALERT] {subject} (Mail Config Missing)")
            return
        
        msg = MIMEText(body)
        msg['Subject'] = f"[URGENT] {subject}"
        msg['From'] = MAIL_SENDER
        msg['To'] = MAIL_RECEIVER
        
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(MAIL_SENDER, MAIL_APP_PASS)
                server.send_message(msg)
            print("[ALERT] Mail Sent.")
        except Exception as e:
            print(f"[ALERT] Mail Failed: {e}")

    def fetch_jit_odds(self):
        print("[JIT] Fetching fresh odds via WorkerCollector...")
        try:
            # Calling worker_collector.py to update Supabase
            # Assuming worker_collector.py is in the same dir
            subprocess.run([sys.executable, "worker_collector.py"], check=True)
            print("[JIT] Fetch Complete.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] JIT Fetch Failed: {e}")
            self.send_alert("JIT Fetch Failed", f"worker_collector failed: {e}")
            raise

    def process_race(self, race_id):
        # 1. Get Latest Data from Supabase
        # We need 0B15 (Card) and 0B31 (Odds)
        # Sort by timestamp desc to get latest
        try:
            res_card = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B15").order("timestamp", desc=True).limit(20).execute() # Get all horses for race
            res_odds = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B31").order("timestamp", desc=True).limit(1).execute() # Get latest odds set
            
            if not res_card.data or not res_odds.data:
                print(f"[SKIP] Missing data for {race_id}")
                return

            # 2. Parse & Align
            odds_data = JVParser.parse_0B31(res_odds.data[0]['content']['raw_string'])
            if not odds_data:
                print("[SKIP] Failed to parse Odds")
                return

            candidates = []
            
            for row in res_card.data:
                card_info = JVParser.parse_0B15(row['content']['raw_string'])
                if not card_info: continue
                
                h_num = card_info['horse_num']
                h_name = card_info['horse_name']
                
                # --- ALIGNMENT CHECK ---
                # Verify that the Odds data for this h_num matches...
                # Since 0B31 usually doesn't have Names, we check count/structure?
                # Or better: We check if h_num exists in Odds.
                if h_num not in odds_data['odds']:
                     # Critical Mismatch or Scratch
                     msg = f"Horse {h_num} ({h_name}) missing in Odds Data. Possible Scratch."
                     print(f"[WARN] {msg}")
                     # If validation requires Strict Name Check, we need name in Odds (rarely present).
                     # Use Bloodline ID if available.
                     continue
                
                current_odds = odds_data['odds'][h_num]
                
                candidates.append({
                    'horse_num': h_num,
                    'horse_name': h_name,
                    'odds': current_odds,
                    'features': card_info['features'] # Pass to Brain
                })
            
            if not candidates:
                return

            # 3. Predict & EV Filter
            df = pd.DataFrame(candidates)
            
            # Brain Prediction (Mock or Real)
            if self.brain:
                # Need to adapt 'features' dict to DF columns expected by Brain
                # For this simplified script, we assume Brain handles it or we map it
                probs = self.brain.model.predict_proba(df)[:, 1] # Simplified
            else:
                # Mock Probability
                probs = np.random.uniform(0, 0.5, size=len(df))
            
            df['ai_prob'] = probs
            df['ev'] = df['ai_prob'] * df['odds']
            
            # 4. Strict Filtering
            hits = df[df['ev'] > EV_THRESHOLD]
            
            if hits.empty:
                print(f"[INFO] Race {race_id}: No bets (Max EV: {df['ev'].max():.2f})")
                return

            # 5. Queue
            queue_items = []
            for _, hit in hits.iterrows():
                print(f" >>> HIT! {hit['horse_name']} (EV {hit['ev']:.2f})")
                
                # Log Content
                log_details = f"Prob:{hit['ai_prob']:.3f} * Odds:{hit['odds']} = EV:{hit['ev']:.2f}"
                
                queue_items.append({
                    "race_id": race_id,
                    "horse_num": int(hit['horse_num']),
                    "bet_type": "WIN",
                    "amount": 100, # Strategy Logic needed here
                    "status": "approved",
                    "created_at": str(datetime.datetime.now()),
                    # "details": log_details # Assuming table has this col, else omit
                })
                
            if queue_items:
                 self.supabase.table("bet_queue").insert(queue_items).execute()
                 print(f"[QUEUE] Inserted {len(queue_items)} bets.")

        except Exception as e:
            print(f"[ERROR] Process Race Failed: {e}")
            self.send_alert("Prediction Aborted", f"Error in {race_id}: {e}")

    def run(self):
        print("[PREDICTOR] Starting Loop...")
        # In production, loop forever or by scheduler
        # Here we run once for demonstration
        self.fetch_jit_odds()
        
        # Identify Active Races (Mocking Race ID)
        active_races = ["202602070501"] 
        
        for rid in active_races:
            self.process_race(rid)

if __name__ == "__main__":
    pred = Predictor()
    pred.run()
