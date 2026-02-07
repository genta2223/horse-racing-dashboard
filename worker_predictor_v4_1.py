"""
JRA Predictor V4.1 - Hybrid Strategy (Cloud Version)
=====================================================
Reads race data from Supabase (uploaded by local collector) and
generates betting predictions.

This runs on Streamlit Cloud or locally.
"""

import os
import sys
import json
import datetime
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client

# Try importing local AI brain (optional)
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
    """Hybrid Strategy Predictor: Spear (Single) + Shield (Wide)"""
    
    def __init__(self):
        print("[PREDICTOR V4.1] Initializing Hybrid Strategy...")
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        if BRAIN_AVAILABLE:
            self.brain = Brain(model_path="local_engine/final_model.pkl")
        else:
            self.brain = None
            print("[WARN] AI Brain not available. Using probability estimation.")
    
    def fetch_latest_data(self, data_type: str, race_date: str = None) -> list:
        """Fetch latest data from Supabase raw_race_data table"""
        try:
            query = self.supabase.table("raw_race_data")\
                .select("*")\
                .eq("data_type", data_type)
            
            if race_date:
                query = query.eq("race_date", race_date)
            
            res = query.order("timestamp", desc=True).limit(100).execute()
            return res.data if res.data else []
        except Exception as e:
            print(f"[ERROR] Failed to fetch {data_type}: {e}")
            return []
    
    def parse_tanpuku_odds(self, raw_string: str) -> dict:
        """Parse 0B31 (Tanpuku odds) from JV-Link format"""
        # JV-Link 0B31 format:
        # Position 0-1: Record type
        # Position 2-17: Race ID
        # Position 18+: Horse odds (variable format)
        
        odds_map = {}
        try:
            # Simplified parsing - actual implementation needs JV-Link spec
            # Each horse's odds is typically 6-8 chars (odds * 10)
            # Example: "000125" = 12.5 odds
            
            # For now, extract what we can
            if len(raw_string) > 50:
                # Try to find numeric patterns for odds
                # This is placeholder - real parser needs spec document
                pass
        except:
            pass
        
        return odds_map
    
    def parse_race_card(self, raw_string: str) -> dict:
        """Parse 0B15 (Race Card) from JV-Link format"""
        # Extract horse numbers, names, weights, etc.
        card = {
            "horse_count": 0,
            "horses": []
        }
        
        try:
            # JV-Link race card contains detailed horse info
            # Actual parsing requires spec document
            pass
        except:
            pass
        
        return card
    
    def estimate_win_probability(self, odds: float, horse_num: int, 
                                  total_horses: int) -> float:
        """Estimate win probability from odds and position"""
        # Simple model: Inverse odds with adjustments
        # Base probability from odds
        base_prob = 1 / odds if odds > 0 else 0
        
        # Adjust for market efficiency (usually overestimate favorites)
        if odds < 5:
            # Favorite: market often overestimates
            adjusted = base_prob * 0.85
        elif odds > 50:
            # Longshot: market often underestimates slightly
            adjusted = base_prob * 1.15
        else:
            adjusted = base_prob
        
        return min(adjusted * 100, 99)  # Return as percentage
    
    def calculate_odds_per_pop(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate odds/popularity ratio for value detection"""
        df = df.sort_values("odds", ascending=True).copy()
        df['pop'] = range(1, len(df) + 1)
        df['odds_per_pop'] = df['odds'] / df['pop']
        return df
    
    def process_race(self, race_id: str, odds_data: list, card_data: list):
        """Process a single race and generate bet recommendations"""
        print(f"\n[RACE] Processing {race_id}...")
        
        # Build horse dataframe
        # For now, use available data or generate reasonable estimates
        horses = []
        
        # Try to extract real odds from data
        for record in odds_data:
            if race_id in record.get("race_id", ""):
                raw = record.get("raw_string", "")
                # Parse odds from raw string
                # Placeholder: generate from content if parseable
                try:
                    content = json.loads(record.get("content", "{}"))
                    # Use parsed data if available
                except:
                    pass
        
        # If no real data, skip or use defaults
        if not horses:
            # Generate placeholder based on typical race
            # In production, this should fail gracefully
            print(f"[SKIP] No parseable odds for {race_id}")
            return []
        
        # Create DataFrame
        race_df = pd.DataFrame(horses)
        
        # Calculate probabilities
        for idx, row in race_df.iterrows():
            prob = self.estimate_win_probability(
                row['odds'], row['horse_num'], len(race_df)
            )
            race_df.at[idx, 'ai_prob'] = prob
        
        # Calculate value metrics
        race_df = self.calculate_odds_per_pop(race_df)
        race_df['ev'] = (race_df['ai_prob'] / 100) * race_df['odds']
        
        # Generate recommendations
        queue_items = []
        
        # ===== SPEAR (Single Bets) =====
        single_hits = race_df[race_df['ev'] >= SINGLE_EV_THRESH]
        for _, h in single_hits.iterrows():
            queue_items.append({
                "race_id": race_id,
                "horse_num": str(int(h['horse_num'])),
                "bet_type": "WIN",
                "amount": 100,
                "status": "approved",
                "details": f"V4.1 Spear EV={h['ev']:.2f} Odds={h['odds']:.1f}"
            })
        
        # ===== SHIELD (Wide Bets) =====
        race_df_sorted = race_df.sort_values("ai_prob", ascending=False)
        if len(race_df_sorted) >= 2:
            axis = race_df_sorted.iloc[0]
            
            for _, partner in race_df_sorted.iloc[1:5].iterrows():  # Top 5 partners
                syn_wide = np.sqrt(axis['odds'] * partner['odds']) * WIDE_ODDS_FACTOR
                prob_joint = (axis['ai_prob']/100) * (partner['ai_prob']/100) * 5.0
                ev_wide = prob_joint * syn_wide
                
                if ev_wide >= WIDE_EV_THRESH:
                    # Check undervalued
                    is_uv = (axis['odds_per_pop'] > 1.2 or partner['odds_per_pop'] > 1.2)
                    if is_uv:
                        queue_items.append({
                            "race_id": race_id,
                            "horse_num": f"{int(axis['horse_num'])}-{int(partner['horse_num'])}",
                            "bet_type": "WIDE",
                            "amount": 100,
                            "status": "approved",
                            "details": f"V4.1 Shield EV={ev_wide:.2f} UV"
                        })
        
        return queue_items
    
    def run(self, target_date: str = None):
        """Main prediction cycle"""
        print("\n" + "="*50)
        print("[PREDICTOR V4.1] Starting Prediction Cycle")
        print("="*50)
        
        if target_date is None:
            target_date = datetime.date.today().strftime("%Y%m%d")
        
        print(f"[TARGET] Date: {target_date}")
        
        # Fetch data from Supabase
        odds_data = self.fetch_latest_data("0B31", target_date)
        card_data = self.fetch_latest_data("0B15", target_date)
        
        print(f"[DATA] Odds records: {len(odds_data)}, Card records: {len(card_data)}")
        
        if not odds_data:
            print("[WARN] No odds data found. Run collector on local PC first.")
            return
        
        # Get unique race IDs
        race_ids = set()
        for record in odds_data:
            rid = record.get("race_id", "")
            if rid:
                race_ids.add(rid[:16])  # Standard race ID length
        
        print(f"[RACES] Found {len(race_ids)} races to process")
        
        # Process each race
        all_bets = []
        for race_id in race_ids:
            bets = self.process_race(race_id, odds_data, card_data)
            all_bets.extend(bets)
        
        # Queue bets to Supabase
        if all_bets:
            try:
                self.supabase.table("bet_queue").insert(all_bets).execute()
                print(f"\n[QUEUED] {len(all_bets)} bets added to queue.")
            except Exception as e:
                print(f"[ERROR] Failed to queue bets: {e}")
        else:
            print("\n[INFO] No bets generated this cycle.")
        
        return all_bets


def run_prediction_cycle():
    """Helper function for background worker"""
    p = PredictorV4_1()
    return p.run()


if __name__ == "__main__":
    predictor = PredictorV4_1()
    predictor.run()
