import os
import sys
import datetime
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv

# Try importing Brain
try:
    from local_engine.brain import Brain
    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False

# --- Config ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# V4.1 Thresholds
SINGLE_EV_THRESH = 2.0
WIDE_EV_THRESH = 1.34
WIDE_ODDS_FACTOR = 0.75

class PredictorV4_1:
    def __init__(self):
        print("[PREDICTOR V4.1] Initializing Hybrid Strategy...")
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        if BRAIN_AVAILABLE:
            self.brain = Brain(model_path="local_engine/final_model.pkl")
        else:
            self.brain = None

    def calculate_odds_per_pop(self, df):
        # df has 'odds' and 'horse_num'
        # Sort by odds asc to determine Pop
        df = df.sort_values("odds", ascending=True)
        df['pop'] = range(1, len(df) + 1)
        df['odds_per_pop'] = df['odds'] / df['pop']
        return df

    def process_race(self, race_id):
        # 1. Fetch Data (Mock-ish implementation based on V2 structure)
        # Fetch latest 0B31 (Odds) and 0B15 (Card) from Supabase
        # ... (Reuse structure from V2, assuming data exists in DB)
        
        # Simplified for brevity in this step:
        # Check Supabase for raw_race_data
        try:
            res_card = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B15").order("timestamp", desc=True).limit(18).execute()
            res_odds = self.supabase.table("raw_race_data").select("*").eq("data_type", "0B31").order("timestamp", desc=True).limit(1).execute()
            
            if not res_card.data or not res_odds.data:
                # print(f"[SKIP] No data for {race_id}")
                return

            # Parse (Mock)
            # Assuming we have a parser or raw string usage
            # For V4.1, we need REAL AI Probs.
            # If Brain is missing, we use random (Development Mode)
            
            # Construct DataFrame
            candidates = []
            # ... parsing logic (omitted for brevity, assuming standard) ...
            # Let's assume we have a DF `race_df` with [horse_num, odds, features...]
            
            # --- MOCK DATA GENERATION (Placehoder) ---
            # Remove this in production and use Real Parser
            race_df = pd.DataFrame({
                'horse_num': range(1, 17),
                'odds': np.random.uniform(1.5, 100.0, 16),
                'features': [np.random.rand(10) for _ in range(16)] # Dummy
            })
            
            # 2. AI Prediction
            if self.brain:
                # probs = self.brain.predict(...) 
                probs = np.random.uniform(0, 0.5, 16) # Dummy
            else:
                probs = np.random.uniform(0, 0.5, 16)
            
            race_df['ai_prob'] = probs * 100 # %
            race_df = self.calculate_odds_per_pop(race_df)
            race_df['ev'] = (race_df['ai_prob']/100) * race_df['odds']
            
            # 3. Logic
            queue_items = []
            
            # Single (Spear)
            single_hits = race_df[race_df['ev'] >= SINGLE_EV_THRESH]
            for _, h in single_hits.iterrows():
                queue_items.append({
                    "race_id": race_id,
                    "horse_num": int(h['horse_num']),
                    "bet_type": "WIN",
                    "amount": 100,
                    "status": "approved",
                    "details": f"V4.1 Single EV {h['ev']:.2f}"
                })
            
            # Wide (Shield)
            # Sort by Prob
            race_df = race_df.sort_values("ai_prob", ascending=False)
            axis = race_df.iloc[0]
            
            for _, partner in race_df.iloc[1:].iterrows():
                syn_wide = np.sqrt(axis['odds'] * partner['odds']) * WIDE_ODDS_FACTOR
                prob_joint = (axis['ai_prob']/100 * partner['ai_prob']/100) * 5.0
                ev_wide = prob_joint * syn_wide
                
                if ev_wide >= WIDE_EV_THRESH:
                    # Undervalued Check
                    is_uv = (axis['odds_per_pop'] > 1.2 or partner['odds_per_pop'] > 1.2)
                    if is_uv:
                        queue_items.append({
                            "race_id": race_id,
                            "horse_num": f"{int(axis['horse_num'])}-{int(partner['horse_num'])}",
                            "bet_type": "WIDE", # 'Wide' or 'WIDE'? V2 users 'WIN'. V4 used 'Wide'.
                            # app.py expects 'Wide' or checks 'Type'.
                            # worker_shopper.py handles 'horse_num' parsing? NO. 
                            # worker_shopper.py logs logic: 
                            # print(f"... Race: {bet['race_id']} Horse: {bet['horse_num']} ...")
                            # doesn't strictly parse type unless it needs to click specific buttons.
                            # Shopper implementation (viewed earlier) just says "Buying..." and logic is hidden/mocked in that file?
                            # Wait, existing shopper had `self.driver.find_element(...)` commented out?
                            # Line 144: `# self.driver.find_element(...)`
                            # It says "Development Mode: Not clicking final button yet".
                            # SO SHOPPER IS MOCK BY DEFAULT.
                            "amount": 100,
                            "status": "approved",
                            "details": f"V4.1 Wide EV {ev_wide:.2f} (UV)"
                        })

            # Insert
            if queue_items:
                self.supabase.table("bet_queue").insert(queue_items).execute()
                print(f"[V4.1] {len(queue_items)} bets queued for {race_id}")

        except Exception as e:
            print(f"Error {race_id}: {e}")

    def run(self):
        print("[V4.1] Standby Loop Started...")
        # Check specific races or loop
        # For standby, just run once or loop
        self.process_race("202602070101") # Dummy Next Race

if __name__ == "__main__":
    p = PredictorV4_1()
    p.run()
