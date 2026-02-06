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

# --- V2 UPGRADE: HIGHER THRESHOLD ---
EV_THRESHOLD = 2.0 # Raised from 1.34 to 2.0 based on Simulation Strategy C

# --- JV Parser (Same as V1) ---
class JVParser:
    """
    Parses fixed-width JV-Data strings.
    offsets should be verified against JRA-VAN SDK spec.
    """
    @staticmethod
    def parse_0B15(raw_str):
        """ Syussouba (Race Card) """
        try:
            # Placeholder MOCK Logic
            # In production, this must handle actual Fixed Width parsing.
            # Assuming row_id (race_id) is handled by collector
            
            # Using basic heuristic if real parsing isn't available:
            # We assume the collector pushed 'content' as valid JSON or we have to parse raw_string.
            # Here we mock parsing for the sake of the Python Logic flow.
            return {
                'race_id': raw_str[0:12] if len(raw_str) > 12 else "Unknown",
                'horse_num': int(raw_str[20:22]) if len(raw_str) > 22 and raw_str[20:22].isdigit() else 0,
                'horse_name': raw_str[30:50].strip() if len(raw_str) > 50 else "Unknown",
                'features': {
                   'prev_3f': 34.5 # Dummy
                }
            }
        except Exception:
            return None

    @staticmethod
    def parse_0B31(raw_str):
        """ Odds (Tan/Fuku) """
        try:
            # Placeholder MOCK Logic
            return {
                'race_id': raw_str[0:12] if len(raw_str) > 12 else "Unknown",
                'odds': {
                    1: 2.5, # Dummy Map
                }
            }
        except:
            return None

class PredictorV2:
    def __init__(self):
        print(f"[PREDICTOR V2] Initializing... EV Threshold: {EV_THRESHOLD}")
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        if BRAIN_AVAILABLE:
            # Model path relative to root
            self.brain = Brain(model_path="local_engine/final_model.pkl")
        else:
            self.brain = None
            
        self.history_df = None 

    def send_alert(self, subject, body):
        if not all([MAIL_SENDER, MAIL_APP_PASS, MAIL_RECEIVER]):
            print(f"[ALERT] {subject} (Mail Config Missing)")
            return
        
        msg = MIMEText(body)
        msg['Subject'] = f"[URGENT V2] {subject}"
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
        print("[JIT] Fetching fresh odds (0B31 + 0B32)...")
        try:
            # Calling worker_collector.py to update Supabase
            # Note: worker_collector now fetches 0B32 as well.
            subprocess.run([sys.executable, "worker_collector.py"], check=True)
            print("[JIT] Fetch Complete.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] JIT Fetch Failed: {e}")
            self.send_alert("JIT Fetch Failed", f"worker_collector failed: {e}")
            raise

    def process_race(self, race_id):
        # 1. Get Latest Data
        try:
            res_card = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B15").order("timestamp", desc=True).limit(20).execute()
            res_odds = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B31").order("timestamp", desc=True).limit(1).execute()
            
            # Future: Get 0B32 for Distortion Analysis
            # res_odds_ren = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B32").order("timestamp", desc=True).limit(1).execute()

            if not res_card.data or not res_odds.data:
                print(f"[SKIP] Missing data for {race_id}")
                return

            # 2. Parse & Align
            odds_data = JVParser.parse_0B31(res_odds.data[0]['content']['raw_string'])
            if not odds_data:
                # If mock string fails, use dummy for V2 Dry Run
                # print("[SKIP] Failed to parse Odds")
                # For safety in Production, we return.
                # For Dry Run without Real Data, we might want to fake it, but let's stick to safe logic.
                return

            candidates = []
            
            for row in res_card.data:
                card_info = JVParser.parse_0B15(row['content']['raw_string'])
                if not card_info: continue
                
                h_num = card_info['horse_num']
                h_name = card_info['horse_name']
                
                # --- ALIGNMENT CHECK ---
                if h_num not in odds_data['odds']:
                     # Check scratches?
                     continue
                
                current_odds = odds_data['odds'][h_num]
                
                candidates.append({
                    'horse_num': h_num,
                    'horse_name': h_name,
                    'odds': current_odds,
                    'features': card_info['features']
                })
            
            if not candidates:
                return

            # 3. Predict & EV Filter (V2 Logic)
            df = pd.DataFrame(candidates)
            
            if self.brain:
                # In production, ensure columns match model
                probs = self.brain.model.predict_proba(df)[:, 1] # Simplified
            else:
                probs = np.random.uniform(0, 0.5, size=len(df))
            
            df['ai_prob'] = probs
            df['ev'] = df['ai_prob'] * df['odds']
            
            # 4. Strict Filtering (EV > 2.0)
            hits = df[df['ev'] > EV_THRESHOLD]
            
            if hits.empty:
                print(f"[INFO] Race {race_id}: No bets (Max EV: {df['ev'].max():.2f})")
                return

            # 5. Queue
            queue_items = []
            for _, hit in hits.iterrows():
                print(f" >>> HIT! {hit['horse_name']} (EV {hit['ev']:.2f})")
                
                queue_items.append({
                    "race_id": race_id,
                    "horse_num": int(hit['horse_num']),
                    "bet_type": "WIN",
                    "amount": 100, # Fixed unit (Shopper handles Cap)
                    "status": "approved",
                    "created_at": str(datetime.datetime.now()),
                    "details": f"V2: EV {hit['ev']:.2f} > 2.0"
                })
                
            if queue_items:
                 self.supabase.table("bet_queue").insert(queue_items).execute()
                 print(f"[QUEUE] Inserted {len(queue_items)} V2 bets.")

        except Exception as e:
            print(f"[ERROR] Process Race Failed: {e}")
            self.send_alert("Prediction Aborted", f"Error in {race_id}: {e}")

    def run(self):
        print("[PREDICTOR V2] Starting Loop (Endurance Mode)...")
        
        # 1. Fetch
        self.fetch_jit_odds()
        
        # 2. Process (Mock ID for now)
        active_races = ["202602070501"] 
        for rid in active_races:
            self.process_race(rid)

if __name__ == "__main__":
    pred = PredictorV2()
    pred.run()
